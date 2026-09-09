package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.BusinessException;
import com.ragstudy.config.RagConfig;
import com.ragstudy.model.dto.DocumentManualRequest;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.vo.DocumentVO;
import com.ragstudy.model.vo.KnowledgeStatsVO;
import com.ragstudy.repository.KnowledgeChunkMapper;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import com.ragstudy.repository.KbKnowledgeBaseMapper;
import org.apache.tika.Tika;
import org.apache.tika.exception.TikaException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 知识库文档管理服务
 *
 * 核心职责：文档的全生命周期管理，包括上传、解析、切片、向量化、索引、检索、删除。
 * 整个处理管线如下：
 *   1. 文档上传 → Apache Tika 提取文本
 *   2. 文本切片 → DocumentChunker 父子切片（child=300字, parent=1000字）
 *   3. 向量化   → EmbeddingService ONNX 本地推理（bge-small-zh, 512维）
 *   4. 写入向量库 → Qdrant（child + parent 双集合）
 *   5. 写入全文索引 → Lucene BM25
 *   6. 持久化到 MySQL（knowledge_document + knowledge_chunk 表）
 *
 * 依赖：DocumentChunker, EmbeddingService, VectorStoreService, Bm25Service, AuditLogService
 */
@Service
public class KnowledgeBaseService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseService.class);

    private final KnowledgeDocumentMapper documentMapper;
    private final KnowledgeChunkMapper chunkMapper;
    private final KbKnowledgeBaseMapper kbMapper;
    private final DocumentChunker documentChunker;
    private final EmbeddingService embeddingService;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final RagConfig ragConfig;
    private final AuditLogService auditLogService;

    public KnowledgeBaseService(KnowledgeDocumentMapper documentMapper,
                                KnowledgeChunkMapper chunkMapper,
                                KbKnowledgeBaseMapper kbMapper,
                                DocumentChunker documentChunker,
                                EmbeddingService embeddingService,
                                VectorStoreService vectorStoreService,
                                Bm25Service bm25Service,
                                RagConfig ragConfig,
                                AuditLogService auditLogService) {
        this.documentMapper = documentMapper;
        this.chunkMapper = chunkMapper;
        this.kbMapper = kbMapper;
        this.documentChunker = documentChunker;
        this.embeddingService = embeddingService;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.ragConfig = ragConfig;
        this.auditLogService = auditLogService;
    }

    /**
     * 上传文档（通用入口）
     * 流程：Tika 解析文本 → 创建数据库记录 → 切片+向量化+索引 → 标记为 indexed
     * 注意：此方法不关联知识库，department/category 仅用于分类标记
     */
    @Transactional
    public DocumentVO uploadDocument(MultipartFile file, String department, String category) {
        String originalFilename = file.getOriginalFilename();
        log.info("开始上传文档: {}, department={}, category={}", originalFilename, department, category);

        String content;
        try {
            content = extractText(file);
        } catch (Exception e) {
            log.error("文档解析失败: {}", originalFilename, e);
            throw new BusinessException("文档解析失败: " + e.getMessage());
        }

        if (content == null || content.isBlank()) {
            throw new BusinessException("文档内容为空");
        }

        KnowledgeDocument document = new KnowledgeDocument();
        document.setFileName(originalFilename);
        document.setFileType(getFileExtension(originalFilename));
        document.setFileSize(file.getSize());
        document.setDepartment(department);
        document.setCategory(category);
        document.setContent(content);
        document.setStatus("processing");
        documentMapper.insert(document);

        log.info("文档记录已创建: id={}", document.getId());

        try {
            processDocument(document, content, "");
            document.setStatus("indexed");
        } catch (Exception e) {
            log.error("文档处理失败: id={}", document.getId(), e);
            document.setStatus("failed");
            documentMapper.updateById(document);
            throw new BusinessException("文档处理失败: " + e.getMessage());
        }

        document.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(document);

        log.info("文档上传完成: id={}, chunks={}, parentChunks={}",
                document.getId(), document.getTotalChunks(), document.getTotalParentChunks());

        auditLogService.log(null, null, "UPLOAD", "DOCUMENT",
                String.valueOf(document.getId()), originalFilename, "文件大小: " + file.getSize(), "SUCCESS");

        return toVO(document);
    }

    /**
     * 文档处理核心管线：切片 → 向量化 → 写入 Qdrant → 写入 BM25
     * 父子双集合策略：child 用于精确检索，parent 用于提供上下文
     */
    private void processDocument(KnowledgeDocument document, String content, String kbName) {
        DocumentChunker.ChunkedDocument chunked = documentChunker.chunk(
                "doc_" + document.getId(), content
        );

        document.setTotalChunks(chunked.childChunks().size());
        document.setTotalParentChunks(chunked.parentChunks().size());

        List<VectorStoreService.VectorEntry> childVectorEntries = new ArrayList<>();
        List<Bm25Service.IndexEntry> bm25Entries = new ArrayList<>();

        List<String> childContents = chunked.childChunks().stream()
                .map(DocumentChunker.ChunkResult::content)
                .collect(Collectors.toList());

        List<float[]> embeddings = embeddingService.embedBatch(childContents);

        for (int i = 0; i < chunked.childChunks().size(); i++) {
            DocumentChunker.ChunkResult chunk = chunked.childChunks().get(i);
            float[] vector = embeddings.get(i);

            KnowledgeChunk chunkEntity = new KnowledgeChunk();
            chunkEntity.setDocumentId(document.getId());
            chunkEntity.setChunkId(chunk.chunkId());
            chunkEntity.setChunkIndex(chunk.chunkIndex());
            chunkEntity.setContent(chunk.content());
            chunkEntity.setContentLength(chunk.content().length());
            chunkEntity.setParentChunkId(chunk.parentChunkId());
            chunkEntity.setParentChunkIndex(chunk.parentChunkIndex());
            chunkMapper.insert(chunkEntity);

            Map<String, Object> payload = new HashMap<>();
            payload.put("documentId", document.getId());
            payload.put("chunkId", chunk.chunkId());
            payload.put("parentChunkId", chunk.parentChunkId());
            payload.put("parentChunkIndex", chunk.parentChunkIndex());
            payload.put("docName", document.getFileName());
            payload.put("kbId", document.getKbId());
            payload.put("kbName", kbName);
            payload.put("department", document.getDepartment());
            payload.put("content", chunk.content());

            childVectorEntries.add(new VectorStoreService.VectorEntry(
                    chunk.chunkId(), vector, payload
            ));

            DocumentChunker.ParentChunk parentChunk = findParentChunk(chunked.parentChunks(), chunk.parentChunkId());
            String parentContent = parentChunk != null ? parentChunk.content() : chunk.content();

            bm25Entries.add(new Bm25Service.IndexEntry(
                    chunk.chunkId(), chunk.content(), parentContent,
                    document.getFileName(), document.getDepartment(), kbName
            ));
        }

        vectorStoreService.ensureCollection(
                ragConfig.getQdrant().getCollectionName(),
                ragConfig.getQdrant().getVectorSize()
        );
        vectorStoreService.upsertBatch(
                ragConfig.getQdrant().getCollectionName(),
                childVectorEntries
        );

        List<VectorStoreService.VectorEntry> parentVectorEntries = new ArrayList<>();
        List<String> parentContents = chunked.parentChunks().stream()
                .map(DocumentChunker.ParentChunk::content)
                .collect(Collectors.toList());
        List<float[]> parentEmbeddings = embeddingService.embedBatch(parentContents);

        for (int i = 0; i < chunked.parentChunks().size(); i++) {
            DocumentChunker.ParentChunk pc = chunked.parentChunks().get(i);
            Map<String, Object> payload = new HashMap<>();
            payload.put("documentId", document.getId());
            payload.put("parentChunkId", pc.parentChunkId());
            payload.put("docName", document.getFileName());
            payload.put("kbId", document.getKbId());
            payload.put("kbName", kbName);
            payload.put("department", document.getDepartment());

            parentVectorEntries.add(new VectorStoreService.VectorEntry(
                    pc.parentChunkId(), parentEmbeddings.get(i), payload
            ));
        }

        vectorStoreService.ensureCollection(
                ragConfig.getQdrant().getParentCollectionName(),
                ragConfig.getQdrant().getVectorSize()
        );
        vectorStoreService.upsertBatch(
                ragConfig.getQdrant().getParentCollectionName(),
                parentVectorEntries
        );

        bm25Service.indexDocuments(bm25Entries);
    }

    private DocumentChunker.ParentChunk findParentChunk(
            List<DocumentChunker.ParentChunk> parentChunks, String parentChunkId) {
        return parentChunks.stream()
                .filter(pc -> pc.parentChunkId().equals(parentChunkId))
                .findFirst()
                .orElse(null);
    }

    /**
     * 使用 Apache Tika 提取文档文本内容（支持 .pdf / .docx / .txt / .md 等格式）
     */
    private String extractText(MultipartFile file) throws IOException, TikaException {
        Tika tika = new Tika();
        try (InputStream is = file.getInputStream()) {
            return tika.parseToString(is);
        }
    }

    private String getFileExtension(String filename) {
        if (filename == null) return "unknown";
        int dot = filename.lastIndexOf('.');
        return dot > 0 ? filename.substring(dot + 1).toLowerCase() : "unknown";
    }

    /**
     * 分页查询文档列表（按 department + category 过滤）
     */
    public Page<DocumentVO> listDocuments(int pageNum, int pageSize, String department, String category, String keyword) {
        LambdaQueryWrapper<KnowledgeDocument> wrapper = new LambdaQueryWrapper<>();
        if (department != null && !department.isBlank()) {
            wrapper.eq(KnowledgeDocument::getDepartment, department);
        }
        if (category != null && !category.isBlank()) {
            wrapper.eq(KnowledgeDocument::getCategory, category);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(KnowledgeDocument::getFileName, keyword));
        }
        wrapper.orderByDesc(KnowledgeDocument::getCreateTime);

        Page<KnowledgeDocument> page = new Page<>(pageNum, pageSize);
        Page<KnowledgeDocument> result = documentMapper.selectPage(page, wrapper);

        Page<DocumentVO> voPage = new Page<>(pageNum, pageSize, result.getTotal());
        voPage.setRecords(result.getRecords().stream()
                .map(this::toVO)
                .collect(Collectors.toList()));
        return voPage;
    }

    /**
     * 删除文档（含向量库、BM25索引、数据库记录）
     */
    @Transactional
    public void deleteDocument(String documentId) {
        Long docId = Long.parseLong(documentId);
        KnowledgeDocument document = documentMapper.selectById(docId);
        if (document == null) {
            throw new BusinessException("文档不存在");
        }

        List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(docId);
        for (KnowledgeChunk chunk : chunks) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId());
            bm25Service.removeDocument(chunk.getChunkId());
        }

        chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>()
                .eq(KnowledgeChunk::getDocumentId, docId));
        documentMapper.deleteById(docId);

        log.info("文档已删除: id={}, chunks={}", documentId, chunks.size());
        auditLogService.log(null, null, "DELETE", "DOCUMENT",
                documentId, document.getFileName(), "删除chunks: " + chunks.size(), "SUCCESS");
    }

    public DocumentVO getDocumentById(String documentId) {
        KnowledgeDocument document = documentMapper.selectById(Long.parseLong(documentId));
        if (document == null) {
            throw new BusinessException("文档不存在");
        }
        return toVO(document);
    }

    public KnowledgeStatsVO getStatistics() {
        long totalDocuments = documentMapper.selectCount(null);
        long totalChunks = chunkMapper.selectCount(null);

        List<KnowledgeDocument> documents = documentMapper.selectList(null);
        long totalSize = documents.stream().mapToLong(d -> d.getFileSize() != null ? d.getFileSize() : 0).sum();
        long indexedCount = documents.stream()
                .filter(d -> "indexed".equals(d.getStatus()))
                .count();
        long pendingCount = documents.stream()
                .filter(d -> !"indexed".equals(d.getStatus()))
                .count();

        return KnowledgeStatsVO.builder()
                .totalDocuments((int) totalDocuments)
                .totalChunks((int) totalChunks)
                .totalSize(totalSize)
                .indexedDocuments((int) indexedCount)
                .pendingDocuments((int) pendingCount)
                .build();
    }

    public List<KnowledgeChunk> getChunksByDocumentId(String documentId) {
        return chunkMapper.selectByDocumentId(Long.parseLong(documentId));
    }

    public KnowledgeChunk getChunkByChunkId(String chunkId) {
        LambdaQueryWrapper<KnowledgeChunk> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(KnowledgeChunk::getChunkId, chunkId);
        return chunkMapper.selectOne(wrapper);
    }

    /**
     * 更新分块内容，并重新向量化 + 重新索引 BM25
     */
    @Transactional
    public void updateChunk(String chunkId, String newContent) {
        KnowledgeChunk chunk = getChunkByChunkId(chunkId);
        if (chunk == null) {
            throw new BusinessException("分块不存在");
        }

        KnowledgeDocument document = documentMapper.selectById(chunk.getDocumentId());

        chunk.setContent(newContent);
        chunk.setContentLength(newContent.length());
        chunkMapper.updateById(chunk);

        float[] newVector = embeddingService.embed(newContent);

        Map<String, Object> payload = new HashMap<>();
        payload.put("documentId", chunk.getDocumentId());
        payload.put("chunkId", chunk.getChunkId());
        payload.put("parentChunkId", chunk.getParentChunkId());
        payload.put("parentChunkIndex", chunk.getParentChunkIndex());
        payload.put("docName", document != null ? document.getFileName() : "");
        payload.put("kbId", document != null ? document.getKbId() : "");
        payload.put("department", document != null ? document.getDepartment() : "");
        payload.put("content", newContent);

        vectorStoreService.upsert(
                ragConfig.getQdrant().getCollectionName(),
                chunk.getChunkId(),
                newVector,
                payload
        );

        bm25Service.removeDocument(chunk.getChunkId());

        List<KnowledgeChunk> siblings = chunkMapper.selectByParentChunkId(chunk.getParentChunkId());
        String parentContent;
        if (siblings != null && !siblings.isEmpty()) {
            StringBuilder sb = new StringBuilder();
            siblings.forEach(c -> sb.append(c.getContent()).append("\n"));
            parentContent = sb.toString().trim();
        } else {
            parentContent = newContent;
        }

        bm25Service.indexDocument(
                chunk.getChunkId(),
                newContent
        );

        log.info("分块已更新: chunkId={}, documentId={}", chunkId, chunk.getDocumentId());
    }

    /**
     * 按知识库ID分页查询文档（支持 keyword/status/fileType 过滤，并关联知识库名称）
     */
    public IPage<DocumentVO> listDocuments(Long kbId, int pageNum, int pageSize, String keyword, String status, String fileType) {
        LambdaQueryWrapper<KnowledgeDocument> wrapper = new LambdaQueryWrapper<>();
        if (kbId != null) {
            wrapper.eq(KnowledgeDocument::getKbId, kbId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(KnowledgeDocument::getFileName, keyword));
        }
        if (StringUtils.hasText(status)) {
            wrapper.eq(KnowledgeDocument::getStatus, status);
        }
        if (StringUtils.hasText(fileType)) {
            wrapper.eq(KnowledgeDocument::getFileType, fileType);
        }
        wrapper.orderByDesc(KnowledgeDocument::getCreateTime);

        Page<KnowledgeDocument> page = new Page<>(pageNum, pageSize);
        Page<KnowledgeDocument> result = documentMapper.selectPage(page, wrapper);

        String kbName = "";
        if (kbId != null) {
            KbKnowledgeBase kb = kbMapper.selectById(kbId);
            if (kb != null) {
                kbName = kb.getName();
            }
        }

        final String finalKbName = kbName;
        Page<DocumentVO> voPage = new Page<>(pageNum, pageSize, result.getTotal());
        voPage.setRecords(result.getRecords().stream().map(doc -> {
            DocumentVO vo = toVO(doc);
            vo.setKnowledgeBaseName(finalKbName);
            return vo;
        }).collect(Collectors.toList()));
        return voPage;
    }

    /**
     * 上传文档到指定知识库（含切片+向量化+索引，状态: PARSING → READY/FAILED）
     */
    @Transactional
    public DocumentVO uploadDocumentToKb(Long kbId, MultipartFile file, String tags) {
        String originalFilename = file.getOriginalFilename();
        log.info("上传文档到知识库: kbId={}, fileName={}", kbId, originalFilename);

        String content;
        try {
            content = extractText(file);
        } catch (Exception e) {
            log.error("文档解析失败: {}", originalFilename, e);
            throw new BusinessException("文档解析失败: " + e.getMessage());
        }

        if (content == null || content.isBlank()) {
            throw new BusinessException("文档内容为空");
        }

        KnowledgeDocument document = new KnowledgeDocument();
        document.setFileName(originalFilename);
        document.setFileType(getFileExtension(originalFilename));
        document.setFileSize(file.getSize());
        document.setKbId(kbId);
        document.setCategory(tags);
        document.setContent(content);
        document.setStatus("PARSING");
        documentMapper.insert(document);

        String kbName = "";
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb != null) {
            kbName = kb.getName();
        }

        try {
            processDocument(document, content, kbName);
            document.setStatus("READY");
        } catch (Exception e) {
            log.error("文档处理失败: id={}", document.getId(), e);
            document.setStatus("FAILED");
            documentMapper.updateById(document);
            throw new BusinessException("文档处理失败: " + e.getMessage());
        }

        document.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(document);

        return toVO(document);
    }

    /**
     * 批量上传文档到知识库，统计成功数量
     */
    @Transactional
    public int batchUploadDocuments(Long kbId, List<MultipartFile> files) {
        int successCount = 0;
        for (MultipartFile file : files) {
            try {
                uploadDocumentToKb(kbId, file, null);
                successCount++;
            } catch (Exception e) {
                log.error("批量上传失败: fileName={}, error={}", file.getOriginalFilename(), e.getMessage());
            }
        }
        return successCount;
    }

    /**
     * 手动录入文档（直接输入文本内容，不使用文件上传）
     */
    @Transactional
    public DocumentVO createManualDocument(Long kbId, DocumentManualRequest request) {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setFileName(request.getTitle() + ".txt");
        document.setFileType("txt");
        document.setFileSize((long) request.getContent().length());
        document.setKbId(kbId);
        document.setCategory(request.getTags());
        document.setContent(request.getContent());
        document.setStatus("PARSING");
        documentMapper.insert(document);

        String kbName = "";
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb != null) {
            kbName = kb.getName();
        }

        try {
            processDocument(document, request.getContent(), kbName);
            document.setStatus("READY");
        } catch (Exception e) {
            log.error("手动录入处理失败: id={}", document.getId(), e);
            document.setStatus("FAILED");
            documentMapper.updateById(document);
            throw new BusinessException("处理失败: " + e.getMessage());
        }

        document.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(document);

        return toVO(document);
    }

    /**
     * 更新文档元信息（fileName / category）
     */
    @Transactional
    public DocumentVO updateDocument(String docId, Map<String, Object> body) {
        KnowledgeDocument document = documentMapper.selectById(Long.parseLong(docId));
        if (document == null) {
            throw new BusinessException("文档不存在");
        }
        if (body.containsKey("fileName")) {
            document.setFileName((String) body.get("fileName"));
        }
        if (body.containsKey("category")) {
            document.setCategory((String) body.get("category"));
        }
        document.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(document);
        return toVO(document);
    }

    /**
     * 重新解析文档：删除旧切片/向量/BM25索引，用原始内容重新进行切片→向量化→索引
     */
    @Transactional
    public void reparseDocument(String docId) {
        Long docIdLong = Long.parseLong(docId);
        KnowledgeDocument document = documentMapper.selectById(docIdLong);
        if (document == null) {
            throw new BusinessException("文档不存在");
        }

        String content = document.getContent();
        if (content == null || content.isBlank()) {
            throw new BusinessException("文档原始内容不存在，无法重新解析，请重新上传文档");
        }

        List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(docIdLong);
        for (KnowledgeChunk chunk : chunks) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId());
            bm25Service.removeDocument(chunk.getChunkId());
        }
        chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>().eq(KnowledgeChunk::getDocumentId, docIdLong));

        document.setStatus("PARSING");
        document.setTotalChunks(0);
        document.setTotalParentChunks(0);
        documentMapper.updateById(document);

        String kbName = "";
        KbKnowledgeBase kb = kbMapper.selectById(document.getKbId());
        if (kb != null) {
            kbName = kb.getName();
        }

        try {
            processDocument(document, content, kbName);
            document.setStatus("READY");
        } catch (Exception e) {
            log.error("重新解析失败: id={}", docId, e);
            document.setStatus("FAILED");
            documentMapper.updateById(document);
            throw new BusinessException("重新解析失败: " + e.getMessage());
        }

        document.setUpdateTime(LocalDateTime.now());
        documentMapper.updateById(document);

        log.info("文档重新解析完成: id={}", docId);
        auditLogService.log(null, null, "REPARSE", "DOCUMENT",
                docId, document.getFileName(), "重新解析完成", "SUCCESS");
    }

    /**
     * 恢复已删除的文档（软删除 → 恢复）
     */
    @Transactional
    public void restoreDocument(String docId) {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setId(Long.parseLong(docId));
        document.setDeleted(0);
        documentMapper.updateById(document);
        log.info("文档已恢复: id={}", docId);
        auditLogService.log(null, null, "RESTORE", "DOCUMENT",
                docId, null, null, "SUCCESS");
    }

    @Transactional
    public void purgeDocument(String docId) {
        Long docIdLong = Long.parseLong(docId);
        List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(docIdLong);
        for (KnowledgeChunk chunk : chunks) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId());
            bm25Service.removeDocument(chunk.getChunkId());
        }
        chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>().eq(KnowledgeChunk::getDocumentId, docIdLong));

        documentMapper.deleteById(docIdLong);
        log.info("文档已彻底删除: id={}, chunks={}", docId, chunks.size());
        auditLogService.log(null, null, "PURGE", "DOCUMENT",
                docId, null, "删除chunks: " + chunks.size(), "SUCCESS");
    }

    private DocumentVO toVO(KnowledgeDocument document) {
        return DocumentVO.builder()
                .id(document.getId())
                .fileName(document.getFileName())
                .fileType(document.getFileType())
                .fileSize(document.getFileSize())
                .department(document.getDepartment())
                .category(document.getCategory())
                .totalChunks(document.getTotalChunks())
                .totalParentChunks(document.getTotalParentChunks())
                .status(document.getStatus())
                .summary(document.getSummary())
                .createTime(document.getCreateTime())
                .knowledgeBaseId(document.getKbId())
                .knowledgeBaseName("")
                .build();
    }
}