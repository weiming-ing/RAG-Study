package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * 混合检索服务
 *
 * 核心职责：编排向量检索（Qdrant）和 BM25 关键词检索（Lucene），加权融合后返回统一结果。
 *
 * 检索流程：
 *   1. 将用户查询向量化 → EmbeddingService.embed()
 *   2. 【并行】向量检索 → Qdrant 余弦相似度检索（权重 0.7）
 *   3. 【并行】BM25 检索 → Lucene 中文分词全文检索（权重 0.3）
 *   4. 加权融合 → 相同 chunk 的分数累加（vectorScore*0.7 + bm25Score*0.3）
 *   5. 去重     → 基于内容归一化去重（避免重复片段）
 *   6. 截断 Top-K 返回
 *
 * 性能优化：
 *   - 向量检索和 BM25 检索通过 CompletableFuture 并行执行，减少约 50% 的响应时间
 *   - 使用虚拟线程（Virtual Thread, JDK 21）执行并行任务，避免线程池争用
 *   - 每种检索独立 try-catch，单侧失败不影响另一侧
 */
@Service
public class HybridSearchService {

    private static final Logger log = LoggerFactory.getLogger(HybridSearchService.class);

    private final RagConfig ragConfig;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final EmbeddingService embeddingService;

    /**
     * 虚拟线程执行器：JDK 21 Virtual Thread，轻量级，适合 IO 密集型并行检索
     */
    private final ExecutorService virtualExecutor = Executors.newVirtualThreadPerTaskExecutor();

    public HybridSearchService(RagConfig ragConfig, VectorStoreService vectorStoreService,
                               Bm25Service bm25Service, EmbeddingService embeddingService) {
        this.ragConfig = ragConfig;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.embeddingService = embeddingService;
    }

    /**
     * 混合检索主入口：并行执行向量检索 + BM25 检索 → 加权融合 → 去重 → Top-K
     * 向量检索和 BM25 检索通过 CompletableFuture 并行执行，
     * 每种检索独立 try-catch，单侧失败不影响另一侧
     */
    public List<SearchResultVO> hybridSearch(String query, int topK, Map<String, String> filters) {
        long t0 = System.currentTimeMillis();

        // 1. 先做 Embedding（向量化，无法并行，前置完成）
        final float[] queryVector = embedQuery(query);

        // 2. 并行执行向量检索 + BM25 检索
        CompletableFuture<List<SearchResultVO>> vectorFuture = CompletableFuture.supplyAsync(() -> {
            if (queryVector == null) return List.<SearchResultVO>of();
            try {
                return vectorStoreService.search(
                        ragConfig.getQdrant().getCollectionName(),
                        queryVector,
                        topK * 2,
                        filters
                );
            } catch (Exception e) {
                log.error("向量检索失败", e);
                return List.<SearchResultVO>of();
            }
        }, virtualExecutor);

        CompletableFuture<List<SearchResultVO>> bm25Future = CompletableFuture.supplyAsync(() -> {
            try {
                return bm25Service.search(query, topK * 2);
            } catch (Exception e) {
                log.error("BM25 检索失败", e);
                return List.<SearchResultVO>of();
            }
        }, virtualExecutor);

        // 3. 等待两个并行任务完成
        List<SearchResultVO> vectorResults;
        List<SearchResultVO> bm25Results;
        try {
            vectorResults = vectorFuture.get(10, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("向量检索超时或异常", e);
            vectorResults = List.of();
        }
        try {
            bm25Results = bm25Future.get(10, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("BM25 检索超时或异常", e);
            bm25Results = List.of();
        }

        // 4. 加权融合
        List<SearchResultVO> merged = mergeResults(vectorResults, bm25Results);

        // 5. 去重
        List<SearchResultVO> deduplicated = deduplicate(merged);

        // 6. 截断 Top-K
        List<SearchResultVO> result = deduplicated.stream()
                .limit(topK)
                .collect(Collectors.toList());

        long elapsed = System.currentTimeMillis() - t0;
        log.info("混合检索完成: query={}, vectorHits={}, bm25Hits={}, merged={}, final={},耗时={}ms",
                query.length(), vectorResults.size(), bm25Results.size(),
                merged.size(), result.size(), elapsed);

        return result;
    }

    /**
     * 加权融合：相同 chunkId 的结果分数累加（vectorScore*weight + bm25Score*weight）
     * 不同 chunkId 的结果各自保留，最终按加权分数降序排列
     */
    private List<SearchResultVO> mergeResults(List<SearchResultVO> vectorResults, List<SearchResultVO> bm25Results) {
        double vectorWeight = ragConfig.getRetrieval().getVectorWeight();
        double bm25Weight = ragConfig.getRetrieval().getBm25Weight();

        Map<String, SearchResultVO> merged = new LinkedHashMap<>();

        for (SearchResultVO r : vectorResults) {
            SearchResultVO weighted = SearchResultVO.builder()
                    .id(r.getId())
                    .chunkId(r.getChunkId())
                    .content(r.getContent())
                    .parentContent(r.getParentContent())
                    .parentChunkId(r.getParentChunkId())
                    .score(r.getScore() * vectorWeight)
                    .metadata(r.getMetadata())
                    .build();
            merged.put(r.getId(), weighted);
        }

        for (SearchResultVO r : bm25Results) {
            if (merged.containsKey(r.getId())) {
                SearchResultVO existing = merged.get(r.getId());
                existing.setScore(existing.getScore() + r.getScore() * bm25Weight);
            } else {
                SearchResultVO weighted = SearchResultVO.builder()
                        .id(r.getId())
                        .chunkId(r.getChunkId())
                        .content(r.getContent())
                        .parentContent(r.getParentContent())
                        .parentChunkId(r.getParentChunkId())
                        .score(r.getScore() * bm25Weight)
                        .metadata(r.getMetadata())
                        .build();
                merged.put(r.getId(), weighted);
            }
        }

        return merged.values().stream()
                .sorted(Comparator.comparingDouble(SearchResultVO::getScore).reversed())
                .collect(Collectors.toList());
    }

    /**
     * 内容去重：将内容去除空白符后取前100字符做归一化，相同内容只保留分数最高的
     */
    private List<SearchResultVO> deduplicate(List<SearchResultVO> results) {
        Set<String> seenContent = new HashSet<>();
        List<SearchResultVO> deduplicated = new ArrayList<>();

        for (SearchResultVO result : results) {
            String normalized = normalizeContent(result.getContent());
            if (seenContent.add(normalized)) {
                deduplicated.add(result);
            }
        }
        return deduplicated;
    }

    private String normalizeContent(String content) {
        if (content == null) return "";
        String stripped = content.replaceAll("\\s+", "");
        return stripped.substring(0, Math.min(stripped.length(), 100));
    }

    /**
     * 执行向量化，失败时返回 null
     * 提取为独立方法以确保 queryVector 是 effectively final，可在 lambda 中使用
     */
    private float[] embedQuery(String query) {
        try {
            return embeddingService.embed(query);
        } catch (Exception e) {
            log.error("Embedding 失败，无法进行向量检索", e);
            return null;
        }
    }
}