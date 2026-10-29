package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.ParseTask;
import com.ragstudy.repository.KnowledgeChunkMapper;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 文档处理管线服务
 *
 * 核心职责：承载「切片 → 向量化 → 写 Qdrant → 写 BM25 → 持久化切片」重管线，
 * 并接通 ParseTaskService 状态机（PENDING→RUNNING→SUCCESS/FAILED）记录处理进度。
 *
 * 异步形态：@Async("parseTaskExecutor")（线程池见 AsyncTaskConfig，此前零调用）
 * 供上传路径使用——上传接口立即返回 PARSING 状态，前端轮询文档状态直到 READY/FAILED。
 * 同步形态：reparseDocument / createManualDocument 沿用原同步语义，共用同一管线。
 *
 * 事务说明：后台线程无外层事务，各 Mapper 写入自动提交——
 * 以文档 status 字段为准（FAILED 即整体失败），避免长时间持有数据库连接。
 */
@Service
public class DocumentProcessService {

    private static final Logger log = LoggerFactory.getLogger(DocumentProcessService.class);

    private final DocumentChunker documentChunker;
    private final EmbeddingService embeddingService;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final ParseTaskService parseTaskService;
    private final KnowledgeChunkMapper chunkMapper;
    private final KnowledgeDocumentMapper documentMapper;
    private final RagConfig ragConfig;

    public DocumentProcessService(DocumentChunker documentChunker,
                                  EmbeddingService embeddingService,
                                  VectorStoreService vectorStoreService,
                                  Bm25Service bm25Service,
                                  ParseTaskService parseTaskService,
                                  KnowledgeChunkMapper chunkMapper,
                                  KnowledgeDocumentMapper documentMapper,
                                  RagConfig ragConfig) {
        this.documentChunker = documentChunker;
        this.embeddingService = embeddingService;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.parseTaskService = parseTaskService;
        this.chunkMapper = chunkMapper;
        this.documentMapper = documentMapper;
        this.ragConfig = ragConfig;
    }

    /**
     * 异步文档处理入口（Spring 代理调用，从上传请求线程剥离）
     *
     * readyStatus: 处理成功后的状态值——旧全局库路径传 "indexed"，
     * KB 路径传 "READY"（两套历史状态约定并存，见 KnowledgeBaseService.STATUS_INDEXED）。
     */
    @Async("parseTaskExecutor")
    public void processDocumentAsync(Long documentId, String content, String kbName, String readyStatus) {
        KnowledgeDocument document = documentMapper.selectById(documentId);
        if (document == null) {
            log.error("异步处理文档时找不到记录: id={}", documentId);
            return;
        }
        String failedStatus = "indexed".equals(readyStatus) ? "failed" : "FAILED";
        try {
            runPipeline(document, content, kbName, readyStatus, failedStatus);
        } catch (Exception e) {
            // runPipeline 内部已落 FAILED 状态，这里兜底防止状态更新本身失败
            log.error("文档异步处理失败: id={}", document.getId(), e);
        }
    }

    /**
     * 完整处理管线（同步执行）：
     * 创建解析任务 → 切片 → 子块向量化+入库 → 父块向量化+入库 → BM25 索引
     * 每个阶段推进 ParseTask 进度，成功/失败落 ParseTask 与文档状态。
     */
    public void runPipeline(KnowledgeDocument document, String content, String kbName,
                            String readyStatus, String failedStatus) {
        ParseTask task = parseTaskService.createTask(String.valueOf(document.getId()), "PROCESS");
        parseTaskService.startTask(task.getId());
        try {
            processDocument(document, content, kbName, task.getId());

            document.setStatus(readyStatus);
            document.setUpdateTime(LocalDateTime.now());
            documentMapper.updateById(document);
            parseTaskService.completeTask(task.getId());
            log.info("文档处理完成: id={}, chunks={}, parentChunks={}, status={}",
                    document.getId(), document.getTotalChunks(), document.getTotalParentChunks(), readyStatus);
        } catch (Exception e) {
            parseTaskService.failTask(task.getId(), e.getMessage());
            document.setStatus(failedStatus);
            document.setUpdateTime(LocalDateTime.now());
            documentMapper.updateById(document);
            throw new IllegalStateException("文档处理失败: " + e.getMessage(), e);
        }
    }

    /**
     * 文档处理核心管线：切片 → 向量化 → 写入 Qdrant → 写入 BM25
     * 父子双集合策略：child 用于精确检索，parent 用于提供上下文
     * taskId 非空时推进各阶段进度（切片 20 → 子块 60 → 父块 85 → BM25 95）
     */
    private void processDocument(KnowledgeDocument document, String content, String kbName, Long taskId) {
        DocumentChunker.ChunkedDocument chunked = documentChunker.chunk(
                "doc_" + document.getId(), content
        );
        if (taskId != null) {
            parseTaskService.updateProgress(taskId, PROGRESS_CHUNKED);
        }

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
            payload.put("chunkIndex", chunk.chunkIndex());
            payload.put("parentChunkId", chunk.parentChunkId());
            payload.put("parentChunkIndex", chunk.parentChunkIndex());
            payload.put("docName", document.getFileName());
            payload.put("kbId", document.getKbId());
            payload.put("kbName", kbName);
            payload.put("department", document.getDepartment());
            payload.put("content", chunk.content());

            DocumentChunker.ParentChunk parentChunk = findParentChunk(chunked.parentChunks(), chunk.parentChunkId());
            String parentContent = parentChunk != null ? parentChunk.content() : chunk.content();
            payload.put("parentContent", parentContent);

            childVectorEntries.add(new VectorStoreService.VectorEntry(
                    chunk.chunkId(), vector, payload
            ));

            bm25Entries.add(new Bm25Service.IndexEntry(
                    chunk.chunkId(), chunk.content(), parentContent,
                    document.getFileName(), document.getDepartment(), kbName,
                    String.valueOf(document.getKbId()), String.valueOf(document.getId())
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
        if (taskId != null) {
            parseTaskService.updateProgress(taskId, PROGRESS_CHILD_EMBEDDED);
        }

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
        if (taskId != null) {
            parseTaskService.updateProgress(taskId, PROGRESS_PARENT_EMBEDDED);
        }

        bm25Service.indexDocuments(bm25Entries);
        if (taskId != null) {
            parseTaskService.updateProgress(taskId, PROGRESS_INDEXED);
        }
    }

    private DocumentChunker.ParentChunk findParentChunk(
            List<DocumentChunker.ParentChunk> parentChunks, String parentChunkId) {
        return parentChunks.stream()
                .filter(pc -> pc.parentChunkId().equals(parentChunkId))
                .findFirst()
                .orElse(null);
    }

    /** 阶段进度：切片 20 → 子块向量化+入库 60 → 父块向量化+入库 85 → BM25 95 */
    static final int PROGRESS_CHUNKED = 20;
    static final int PROGRESS_CHILD_EMBEDDED = 60;
    static final int PROGRESS_PARENT_EMBEDDED = 85;
    static final int PROGRESS_INDEXED = 95;
}
