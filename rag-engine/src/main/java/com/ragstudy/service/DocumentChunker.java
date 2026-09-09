package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 文档切片服务
 *
 * 核心职责：将长文本切分为父子双层切片。
 *
 * 父子切片策略：
 *   - Child Chunk（子切片，默认 300 字）：用于精确检索，overlap=50 保证上下文连贯
 *   - Parent Chunk（父切片，默认 1000 字）：用于提供更大的上下文窗口
 *   - 切片边界优先在句号处断开，保证语义完整性
 *
 * 数据结构：
 *   - ChunkResult: 子切片（chunkId, content, chunkIndex, parentChunkId, parentChunkIndex）
 *   - ParentChunk: 父切片（parentChunkId, content, parentChunkIndex）
 *   - ChunkedDocument: 完整切片结果（documentId, childChunks, parentChunks）
 */
@Service
public class DocumentChunker {

    private static final Logger log = LoggerFactory.getLogger(DocumentChunker.class);

    private final RagConfig ragConfig;

    public DocumentChunker(RagConfig ragConfig) {
        this.ragConfig = ragConfig;
    }

    public record ChunkResult(
            String chunkId,
            String content,
            int chunkIndex,
            String parentChunkId,
            int parentChunkIndex
    ) {}

    public record ChunkedDocument(
            String documentId,
            List<ChunkResult> childChunks,
            List<ParentChunk> parentChunks
    ) {}

    public record ParentChunk(
            String parentChunkId,
            String content,
            int parentChunkIndex
    ) {}

    /**
     * 文档切片主方法：将文本按父子双层策略切分
     * 外层循环：按 parentSize 切父切片 → 内层循环：按 childSize 切子切片
     * 边界优先在句号处断开，保证语义完整性
     */
    public ChunkedDocument chunk(String documentId, String content) {
        int childSize = ragConfig.getChunker().getChildSize();
        int parentSize = ragConfig.getChunker().getParentSize();
        int overlap = ragConfig.getChunker().getOverlap();

        log.info("开始文档分块: docId={}, childSize={}, parentSize={}, overlap={}",
                documentId, childSize, parentSize, overlap);

        List<ChunkResult> childChunks = new ArrayList<>();
        List<ParentChunk> parentChunks = new ArrayList<>();

        String cleanContent = content.replaceAll("\\s+", " ").trim();
        int totalLength = cleanContent.length();

        if (totalLength == 0) {
            log.warn("文档内容为空");
            return new ChunkedDocument(documentId, childChunks, parentChunks);
        }

        int parentIndex = 0;
        int childIndex = 0;

        int parentStart = 0;
        while (parentStart < totalLength) {
            int parentEnd = Math.min(parentStart + parentSize, totalLength);
            if (parentEnd < totalLength) {
                int lastPeriod = cleanContent.lastIndexOf("。", parentEnd);
                if (lastPeriod > parentStart + childSize) {
                    parentEnd = lastPeriod + 1;
                }
            }
            String parentContent = cleanContent.substring(parentStart, parentEnd).trim();
            String parentChunkId = documentId + "_parent_" + parentIndex;

            parentChunks.add(new ParentChunk(parentChunkId, parentContent, parentIndex));

            int childStart = parentStart;
            while (childStart < parentEnd) {
                int childEnd = Math.min(childStart + childSize, parentEnd);
                if (childEnd < parentEnd) {
                    int lastPeriod = cleanContent.lastIndexOf("。", childEnd);
                    if (lastPeriod > childStart + childSize / 2) {
                        childEnd = lastPeriod + 1;
                    }
                }
                String childContent = cleanContent.substring(childStart, childEnd).trim();
                String childChunkId = documentId + "_child_" + childIndex;

                childChunks.add(new ChunkResult(
                        childChunkId, childContent, childIndex, parentChunkId, parentIndex
                ));

                childIndex++;
                int nextChildStart = childEnd - overlap;
                if (nextChildStart <= childStart || nextChildStart >= parentEnd) {
                    break;
                }
                childStart = nextChildStart;
            }

            parentIndex++;
            parentStart = parentEnd;
        }

        log.info("文档分块完成: docId={}, childChunks={}, parentChunks={}",
                documentId, childChunks.size(), parentChunks.size());

        return new ChunkedDocument(documentId, childChunks, parentChunks);
    }
}