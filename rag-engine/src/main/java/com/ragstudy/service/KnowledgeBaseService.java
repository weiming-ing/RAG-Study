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
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
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

    /** 文档状态：解析并索引成功 */
    private static final String STATUS_READY = "READY";
    /** 文档状态：未提取到正文，需要 OCR（典型为扫描件 PDF） */
    private static final String STATUS_NEEDS_OCR = "NEEDS_OCR";
    /** 视为"已完成"的状态别名（历史实现同时存在 indexed 与 READY 两套写法） */
    private static final Set<String> STATUS_INDEXED = Set.of("indexed", "ready", "completed");
    /** 提取文本短于该长度即认为未获得有效正文 */
    private static final int MIN_EXTRACTED_TEXT_LENGTH = 20;
    /** 无文本层时最可能的文件类型（扫描件） */
    private static final Set<String> SCANNABLE_FILE_TYPES =
            Set.of("pdf", "png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp");

    private final KnowledgeDocumentMapper documentMapper;
    private final KnowledgeChunkMapper chunkMapper;
    private final KbKnowledgeBaseMapper kbMapper;
    private final DocumentChunker documentChunker;
    private final EmbeddingService embeddingService;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final RagConfig ragConfig;
    private final AuditLogService auditLogService;
    private final DocumentProcessService documentProcessService;

    public KnowledgeBaseService(KnowledgeDocumentMapper documentMapper,
                                KnowledgeChunkMapper chunkMapper,
                                KbKnowledgeBaseMapper kbMapper,
                                DocumentChunker documentChunker,
                                EmbeddingService embeddingService,
                                VectorStoreService vectorStoreService,
                                Bm25Service bm25Service,
                                RagConfig ragConfig,
                                AuditLogService auditLogService,
                                DocumentProcessService documentProcessService) {
        this.documentMapper = documentMapper;
        this.chunkMapper = chunkMapper;
        this.kbMapper = kbMapper;
        this.documentChunker = documentChunker;
        this.embeddingService = embeddingService;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.ragConfig = ragConfig;
        this.auditLogService = auditLogService;
        this.documentProcessService = documentProcessService;
    }

    /**
     * 上传文档（通用入口，不关联知识库）
     *
     * parsedContent: Python 端 Docling 预解析的结构化 Markdown。
     * 若不为空则直接使用，跳过 Tika 纯文本提取；否则降级到 Tika 兜底。
     */
    @Transactional
    public DocumentVO uploadDocument(MultipartFile file, String department, String category) {
        return uploadDocument(file, department, category, null);
    }

    @Transactional
    public DocumentVO uploadDocument(MultipartFile file, String department, String category, String parsedContent) {
        String originalFilename = file.getOriginalFilename();
        boolean fromDocling = parsedContent != null && !parsedContent.isBlank();
        log.info("开始上传文档: {}, department={}, category={}, source={}", originalFilename, department, category,
                fromDocling ? "Docling Markdown" : "Java Tika");

        String content;
        if (fromDocling) {
            content = parsedContent;
        } else {
            try {
                content = extractText(file);
            } catch (Exception e) {
                log.error("文档解析失败: {}", originalFilename, e);
                throw new BusinessException("文档解析失败: " + e.getMessage());
            }
        }

        if (hasNoExtractableText(content)) {
            return saveNeedsOcrDocument(originalFilename, file, null, department, category, content);
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

        log.info("文档记录已创建，转入后台异步处理: id={}", document.getId());

        // 重管线（切片/向量化/索引）剥离到 parseTaskExecutor 后台执行，
        // 上传请求立即返回 PARSING 语义状态，前端按 status 轮询
        submitAfterCommit(() -> documentProcessService.processDocumentAsync(document.getId(), content, "", "indexed"));

        auditLogService.log(null, null, "UPLOAD", "DOCUMENT",
                String.valueOf(document.getId()), originalFilename, "文件大小: " + file.getSize(), "SUCCESS");

        return toVO(document);
    }

    /**
     * 文档处理核心管线（同步，供重新解析/手动录入等路径使用）。
     * 管线实现已移交 DocumentProcessService（含 ParseTask 进度跟踪）；
     * 上传路径走其 @Async 入口，不再经过本方法。
     */
    private void processDocument(KnowledgeDocument document, String content, String kbName) {
        documentProcessService.runPipeline(document, content, kbName, STATUS_READY, "FAILED");
    }

    /**
     * 事务提交后再提交异步任务。
     *
     * 上传方法带 @Transactional：若在事务内直接提交 @Async 任务，parse 线程可能
     * 先于 commit 执行 selectById，读不到未提交的文档行而静默放弃（竞态，偶发）。
     * 注册 afterCommit 回调保证异步任务只在数据可见后启动；无事务时立即执行。
     */
    private void submitAfterCommit(Runnable task) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    task.run();
                }
            });
        } else {
            task.run();
        }
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

    /**
     * 判断是否"未提取到有效正文"。
     *
     * 最典型的场景是扫描件 PDF：文件本身有内容（整页是图片），但没有文本层，
     * Tika 只能提取到空串或零星字符。此时若按普通流程处理，文档会入库成功却
     * 永远检索不到——这正是交付演示中最容易翻车的地方。
     */
    private boolean hasNoExtractableText(String content) {
        return content == null || content.strip().length() < MIN_EXTRACTED_TEXT_LENGTH;
    }

    /** 无文本层时，是否属于最可能是扫描件的文件类型 */
    private boolean isLikelyScanned(String filename) {
        return SCANNABLE_FILE_TYPES.contains(getFileExtension(filename));
    }

    /**
     * 未提取到正文时的落库处理：保存为 NEEDS_OCR 状态并给出可操作提示。
     *
     * 为什么不直接抛异常：抛异常只会让前端弹一次瞬时提示、文档不出现在列表里，
     * 管理员无从知道"到底哪些文件需要 OCR"。落库后可在文档列表集中看到并处理。
     *
     * 注意：当前版本未保存原始文件（只保存提取出的文本），因此接入 OCR 引擎后
     * 需要重新上传这些文档；如需支持原地补 OCR，应先把原始文件持久化。
     */
    private DocumentVO saveNeedsOcrDocument(String originalFilename, MultipartFile file,
                                            Long kbId, String department, String category,
                                            String content) {
        KnowledgeDocument document = new KnowledgeDocument();
        document.setFileName(originalFilename);
        document.setFileType(getFileExtension(originalFilename));
        document.setFileSize(file.getSize());
        document.setKbId(kbId);
        document.setDepartment(department);
        document.setCategory(category);
        document.setContent(content);
        document.setTotalChunks(0);
        document.setTotalParentChunks(0);
        document.setStatus(STATUS_NEEDS_OCR);
        documentMapper.insert(document);

        int extracted = content == null ? 0 : content.strip().length();
        String hint = isLikelyScanned(originalFilename)
                ? "疑似扫描件（无文本层），当前版本不含 OCR 引擎，无法提取正文"
                : "未提取到有效正文（内容为空或过短）";

        log.warn("文档未提取到正文，已标记为 {}: id={}, fileName={}, 提取长度={}, 原因={}",
                STATUS_NEEDS_OCR, document.getId(), originalFilename, extracted, hint);

        auditLogService.log(null, null, "UPLOAD", "DOCUMENT",
                String.valueOf(document.getId()), originalFilename,
                "需要 OCR：" + hint, "WARNING");

        return toVO(document);
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

        Set<String> parentChunkIds = chunks.stream()
                .map(KnowledgeChunk::getParentChunkId)
                .filter(id -> id != null && !id.isEmpty())
                .collect(Collectors.toSet());
        for (String parentChunkId : parentChunkIds) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getParentCollectionName(), parentChunkId);
        }

        chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>()
                .eq(KnowledgeChunk::getDocumentId, docId));
        documentMapper.deleteById(docId);

        log.info("文档已删除: id={}, chunks={}, parentChunks={}", documentId, chunks.size(), parentChunkIds.size());
        auditLogService.log(null, null, "DELETE", "DOCUMENT",
                documentId, document.getFileName(),
                "删除chunks: " + chunks.size() + ", parentChunks: " + parentChunkIds.size(), "SUCCESS");
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
        // 注意：历史上两条上传链路分别写入 "indexed" 与 "READY"，
        // 只判断其中一个会把按知识库上传的文档误计为"待处理"。
        long indexedCount = documents.stream()
                .filter(d -> d.getStatus() != null
                        && STATUS_INDEXED.contains(d.getStatus().toLowerCase()))
                .count();
        long pendingCount = totalDocuments - indexedCount;

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

        bm25Service.indexDocuments(List.of(new Bm25Service.IndexEntry(
                chunk.getChunkId(),
                newContent,
                parentContent,
                document != null ? document.getFileName() : "",
                document != null ? document.getDepartment() : "",
                "",  // kbName not available in updateChunk, retrieved separately if needed
                document != null ? String.valueOf(document.getKbId()) : "",
                String.valueOf(chunk.getDocumentId())
        )));

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
     *
     * parsedContent: Python 端 Docling 预解析的结构化 Markdown。
     * 若不为空则直接使用，跳过 Tika 纯文本提取；否则降级到 Tika 兜底。
     */
    @Transactional
    public DocumentVO uploadDocumentToKb(Long kbId, MultipartFile file, String tags) {
        return uploadDocumentToKb(kbId, file, tags, null);
    }

    @Transactional
    public DocumentVO uploadDocumentToKb(Long kbId, MultipartFile file, String tags, String parsedContent) {
        String originalFilename = file.getOriginalFilename();
        boolean fromDocling = parsedContent != null && !parsedContent.isBlank();
        log.info("上传文档到知识库: kbId={}, fileName={}, source={}", kbId, originalFilename,
                fromDocling ? "Docling Markdown" : "Java Tika");

        String content;
        if (fromDocling) {
            content = parsedContent;
        } else {
            try {
                content = extractText(file);
            } catch (Exception e) {
                log.error("文档解析失败: {}", originalFilename, e);
                throw new BusinessException("文档解析失败: " + e.getMessage());
            }
        }

        if (hasNoExtractableText(content)) {
            return saveNeedsOcrDocument(originalFilename, file, kbId, null, tags, content);
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

        // 重管线（切片/向量化/索引）剥离到 parseTaskExecutor 后台执行，
        // 上传请求立即返回 PARSING 状态，前端按 status 轮询
        final String kbNameFinal = kbName;
        submitAfterCommit(() -> documentProcessService.processDocumentAsync(document.getId(), content, kbNameFinal, STATUS_READY));

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
            document.setStatus(STATUS_READY);
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
        Set<String> parentChunkIds = chunks.stream()
                .map(KnowledgeChunk::getParentChunkId)
                .filter(id -> id != null && !id.isEmpty())
                .collect(Collectors.toSet());
        for (String parentChunkId : parentChunkIds) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getParentCollectionName(), parentChunkId);
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
            document.setStatus(STATUS_READY);
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

        Set<String> parentChunkIds = chunks.stream()
                .map(KnowledgeChunk::getParentChunkId)
                .filter(id -> id != null && !id.isEmpty())
                .collect(Collectors.toSet());
        for (String parentChunkId : parentChunkIds) {
            vectorStoreService.deleteById(ragConfig.getQdrant().getParentCollectionName(), parentChunkId);
        }

        chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>().eq(KnowledgeChunk::getDocumentId, docIdLong));

        documentMapper.deleteById(docIdLong);
        log.info("文档已彻底删除: id={}, chunks={}, parentChunks={}", docId, chunks.size(), parentChunkIds.size());
        auditLogService.log(null, null, "PURGE", "DOCUMENT",
                docId, null,
                "删除chunks: " + chunks.size() + ", parentChunks: " + parentChunkIds.size(), "SUCCESS");
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
                .content(document.getContent())
                .createTime(document.getCreateTime())
                .knowledgeBaseId(document.getKbId())
                .knowledgeBaseName("")
                .build();
    }
}