package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.BusinessException;
import com.ragstudy.config.RagConfig;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.repository.KnowledgeChunkMapper;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class ChunkService {

    private static final Logger log = LoggerFactory.getLogger(ChunkService.class);

    private final KnowledgeChunkMapper chunkMapper;
    private final KnowledgeDocumentMapper documentMapper;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final EmbeddingService embeddingService;
    private final RagConfig ragConfig;
    private final AuditLogService auditLogService;

    public ChunkService(KnowledgeChunkMapper chunkMapper,
                        KnowledgeDocumentMapper documentMapper,
                        VectorStoreService vectorStoreService,
                        Bm25Service bm25Service,
                        EmbeddingService embeddingService,
                        RagConfig ragConfig,
                        AuditLogService auditLogService) {
        this.chunkMapper = chunkMapper;
        this.documentMapper = documentMapper;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.embeddingService = embeddingService;
        this.ragConfig = ragConfig;
        this.auditLogService = auditLogService;
    }

    public IPage<KnowledgeChunk> listChunks(int pageNum, int pageSize, String documentId, String keyword) {
        Page<KnowledgeChunk> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<KnowledgeChunk> wrapper = new LambdaQueryWrapper<>();

        if (documentId != null && !documentId.isBlank()) {
            wrapper.eq(KnowledgeChunk::getDocumentId, documentId);
        }
        if (keyword != null && !keyword.isBlank()) {
            wrapper.like(KnowledgeChunk::getContent, keyword);
        }
        wrapper.orderByAsc(KnowledgeChunk::getDocumentId, KnowledgeChunk::getChunkIndex);

        return chunkMapper.selectPage(page, wrapper);
    }

    public KnowledgeChunk getChunkByChunkId(String chunkId) {
        LambdaQueryWrapper<KnowledgeChunk> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(KnowledgeChunk::getChunkId, chunkId);
        return chunkMapper.selectOne(wrapper);
    }

    @Transactional
    public void updateChunkContent(String chunkId, String newContent) {
        KnowledgeChunk chunk = getChunkByChunkId(chunkId);
        if (chunk == null) {
            throw new BusinessException("切片不存在");
        }

        chunk.setContent(newContent);
        chunk.setContentLength(newContent.length());
        chunkMapper.updateById(chunk);

        float[] newVector = embeddingService.embed(newContent);
        Map<String, Object> payload = buildPayload(chunk);
        vectorStoreService.upsert(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId(), newVector, payload);

        bm25Service.removeDocument(chunk.getChunkId());
        bm25Service.indexDocument(chunk.getChunkId(), chunk.getContent());

        log.info("切片已更新并重新向量化: chunkId={}", chunkId);
    }

    @Transactional
    public KnowledgeChunk splitChunk(String chunkId, int splitPosition) {
        KnowledgeChunk chunk = getChunkByChunkId(chunkId);
        if (chunk == null) {
            throw new BusinessException("切片不存在");
        }

        String content = chunk.getContent();
        if (splitPosition <= 0 || splitPosition >= content.length()) {
            throw new BusinessException("分割位置无效，必须在 1 到 " + (content.length() - 1) + " 之间");
        }

        String part1 = content.substring(0, splitPosition).trim();
        String part2 = content.substring(splitPosition).trim();

        if (part1.isEmpty() || part2.isEmpty()) {
            throw new BusinessException("分割后出现空内容");
        }

        chunk.setContent(part1);
        chunk.setContentLength(part1.length());
        chunkMapper.updateById(chunk);

        KnowledgeChunk newChunk = new KnowledgeChunk();
        newChunk.setDocumentId(chunk.getDocumentId());
        newChunk.setChunkId(chunk.getChunkId() + "_split_" + System.currentTimeMillis());
        newChunk.setChunkIndex(chunk.getChunkIndex() + 1);
        newChunk.setContent(part2);
        newChunk.setContentLength(part2.length());
        newChunk.setParentChunkId(chunk.getParentChunkId());
        newChunk.setParentChunkIndex(chunk.getParentChunkIndex());
        chunkMapper.insert(newChunk);

        reindexChunks(chunk.getDocumentId());

        reVectorizeChunk(chunk);
        reVectorizeChunk(newChunk);

        KnowledgeDocument doc = documentMapper.selectById(chunk.getDocumentId());
        if (doc != null) {
            doc.setTotalChunks(chunkMapper.selectByDocumentId(doc.getId()).size());
            documentMapper.updateById(doc);
        }

        log.info("切片已分割: original={}, new={}, position={}", chunkId, newChunk.getChunkId(), splitPosition);
        return newChunk;
    }

    @Transactional
    public KnowledgeChunk mergeChunks(String chunkId1, String chunkId2) {
        KnowledgeChunk chunk1 = getChunkByChunkId(chunkId1);
        KnowledgeChunk chunk2 = getChunkByChunkId(chunkId2);

        if (chunk1 == null || chunk2 == null) {
            throw new BusinessException("切片不存在");
        }
        if (!chunk1.getDocumentId().equals(chunk2.getDocumentId())) {
            throw new BusinessException("不能合并不同文档的切片");
        }

        String mergedContent = chunk1.getContent() + "\n" + chunk2.getContent();
        chunk1.setContent(mergedContent);
        chunk1.setContentLength(mergedContent.length());
        chunkMapper.updateById(chunk1);

        deleteChunkVector(chunk2.getChunkId());
        chunkMapper.deleteById(chunk2.getId());

        reindexChunks(chunk1.getDocumentId());
        reVectorizeChunk(chunk1);

        KnowledgeDocument doc = documentMapper.selectById(chunk1.getDocumentId());
        if (doc != null) {
            doc.setTotalChunks(chunkMapper.selectByDocumentId(doc.getId()).size());
            documentMapper.updateById(doc);
        }

        log.info("切片已合并: {} + {} -> {}", chunkId1, chunkId2, chunkId1);
        return chunk1;
    }

    @Transactional
    public void deleteChunkVector(String chunkId) {
        KnowledgeChunk chunk = getChunkByChunkId(chunkId);
        if (chunk == null) {
            throw new BusinessException("切片不存在");
        }
        vectorStoreService.deleteById(ragConfig.getQdrant().getCollectionName(), chunkId);
        bm25Service.removeDocument(chunkId);
        chunkMapper.deleteById(chunk.getId());

        KnowledgeDocument doc = documentMapper.selectById(chunk.getDocumentId());
        if (doc != null) {
            doc.setTotalChunks(chunkMapper.selectByDocumentId(doc.getId()).size());
            documentMapper.updateById(doc);
        }
        log.info("切片向量已删除: chunkId={}", chunkId);
    }

    @Transactional
    public void reVectorizeChunk(KnowledgeChunk chunk) {
        float[] vector = embeddingService.embed(chunk.getContent());
        Map<String, Object> payload = buildPayload(chunk);
        vectorStoreService.upsert(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId(), vector, payload);

        bm25Service.removeDocument(chunk.getChunkId());
        bm25Service.indexDocument(chunk.getChunkId(), chunk.getContent());
    }

    @Transactional
    public void rebuildKbVectors(Long kbId) {
        LambdaQueryWrapper<KnowledgeDocument> docWrapper = new LambdaQueryWrapper<>();
        docWrapper.eq(KnowledgeDocument::getKbId, kbId);
        List<KnowledgeDocument> documents = documentMapper.selectList(docWrapper);

        int totalProcessed = 0;
        for (KnowledgeDocument doc : documents) {
            List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(doc.getId());
            List<VectorStoreService.VectorEntry> entries = new ArrayList<>();

            for (KnowledgeChunk chunk : chunks) {
                float[] vector = embeddingService.embed(chunk.getContent());
                Map<String, Object> payload = buildPayload(chunk);
                entries.add(new VectorStoreService.VectorEntry(chunk.getChunkId(), vector, payload));
            }

            if (!entries.isEmpty()) {
                vectorStoreService.upsertBatch(ragConfig.getQdrant().getCollectionName(), entries);
            }
            totalProcessed += chunks.size();
        }

        log.info("知识库向量重建完成: kbId={}, documents={}, chunks={}", kbId, documents.size(), totalProcessed);
    }

    public Map<String, Object> getVectorSyncStatus(Long kbId) {
        LambdaQueryWrapper<KnowledgeDocument> docWrapper = new LambdaQueryWrapper<>();
        docWrapper.eq(KnowledgeDocument::getKbId, kbId);
        List<KnowledgeDocument> documents = documentMapper.selectList(docWrapper);

        int totalDocs = documents.size();
        int totalChunks = 0;
        int readyDocs = 0;
        int failedDocs = 0;

        for (KnowledgeDocument doc : documents) {
            List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(doc.getId());
            totalChunks += chunks.size();
            if ("READY".equals(doc.getStatus())) {
                readyDocs++;
            } else if ("FAILED".equals(doc.getStatus())) {
                failedDocs++;
            }
        }

        Map<String, Object> status = new LinkedHashMap<>();
        status.put("totalDocuments", totalDocs);
        status.put("totalChunks", totalChunks);
        status.put("readyDocuments", readyDocs);
        status.put("failedDocuments", failedDocs);
        status.put("collectionName", ragConfig.getQdrant().getCollectionName());
        return status;
    }

    private void reindexChunks(Long documentId) {
        List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(documentId);
        for (int i = 0; i < chunks.size(); i++) {
            KnowledgeChunk c = chunks.get(i);
            if (c.getChunkIndex() != i) {
                c.setChunkIndex(i);
                chunkMapper.updateById(c);
            }
        }
    }

    private Map<String, Object> buildPayload(KnowledgeChunk chunk) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("documentId", chunk.getDocumentId());
        payload.put("chunkId", chunk.getChunkId());
        payload.put("parentChunkId", chunk.getParentChunkId());
        payload.put("parentChunkIndex", chunk.getParentChunkIndex());
        payload.put("chunkIndex", chunk.getChunkIndex());
        payload.put("content", chunk.getContent());
        return payload;
    }
}