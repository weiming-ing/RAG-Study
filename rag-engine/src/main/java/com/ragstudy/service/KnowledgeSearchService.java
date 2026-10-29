package com.ragstudy.service;

import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.model.vo.SearchResultVO;
import com.ragstudy.repository.KbKnowledgeBaseMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 知识检索服务（检索入口门面）
 *
 * 核心职责：作为检索的统一入口，协调 HybridSearchService 和 MultiHopService，
 * 根据参数决定使用单次混合检索还是多跳检索。
 * 支持按 kbId 加载 KB 级检索配置（vectorWeight/bm25Weight/similarityThreshold/enableRerank/filterLowScore），
 * 覆盖全局 RagConfig 默认值。
 */
@Service
public class KnowledgeSearchService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeSearchService.class);

    private final HybridSearchService hybridSearchService;
    private final RerankerService rerankerService;
    private final MultiHopService multiHopService;
    private final KbKnowledgeBaseMapper kbMapper;
    private final com.ragstudy.config.RagConfig ragConfig;

    public KnowledgeSearchService(HybridSearchService hybridSearchService,
                                  RerankerService rerankerService,
                                  MultiHopService multiHopService,
                                  KbKnowledgeBaseMapper kbMapper,
                                  com.ragstudy.config.RagConfig ragConfig) {
        this.hybridSearchService = hybridSearchService;
        this.rerankerService = rerankerService;
        this.multiHopService = multiHopService;
        this.kbMapper = kbMapper;
        this.ragConfig = ragConfig;
    }

    public SearchResponseVO search(String query, int topK, boolean enableHybrid, Map<String, String> filters) {
        long startTime = System.currentTimeMillis();

        log.info("开始检索: query={}, topK={}, hybrid={}", query, topK, enableHybrid);

        List<SearchResultVO> results;
        if (enableHybrid) {
            results = hybridSearchService.hybridSearch(query, topK, filters);
        } else {
            results = new ArrayList<>();
        }

        double latency = (System.currentTimeMillis() - startTime) / 1000.0;

        log.info("检索完成: hits={}, latency={}s", results.size(), latency);

        return SearchResponseVO.builder()
                .results(results)
                .latency(latency)
                .totalHits(results.size())
                .build();
    }

    public SearchResponseVO searchWithRerank(String query, int topK, boolean enableHybrid,
                                              Map<String, String> filters, int rerankTopK) {
        long startTime = System.currentTimeMillis();

        log.info("开始检索+重排序: query={}, topK={}, rerankTopK={}", query, topK, rerankTopK);

        List<SearchResultVO> candidates;
        if (enableHybrid) {
            candidates = hybridSearchService.hybridSearch(query, rerankTopK, filters);
        } else {
            candidates = new ArrayList<>();
        }

        List<SearchResultVO> results = rerankerService.rerank(query, candidates, topK);

        double latency = (System.currentTimeMillis() - startTime) / 1000.0;

        log.info("检索+重排序完成: hits={}, latency={}s", results.size(), latency);

        return SearchResponseVO.builder()
                .results(results)
                .latency(latency)
                .totalHits(results.size())
                .build();
    }

    public SearchResponseVO multiHopSearch(String query, int topK, Map<String, String> filters) {
        long startTime = System.currentTimeMillis();

        List<SearchResultVO> results = multiHopService.multiHopSearch(query, topK, filters);

        double latency = (System.currentTimeMillis() - startTime) / 1000.0;

        return SearchResponseVO.builder()
                .results(results)
                .latency(latency)
                .totalHits(results.size())
                .build();
    }

    /**
     * 多知识库范围检索（三级可见级别的服务端强制范围）。
     * 多 KB 不套用单一 KB 检索配置，使用全局默认权重/阈值。
     * kbIds 以 "kbIds"="1,2,3" 形式并入 filters，由向量(Qdrant OR 组)与 BM25(集合包含)两侧过滤。
     */
    public SearchResponseVO searchInKbs(String query, int topK, boolean enableHybrid,
                                        Map<String, String> filters, List<Long> kbIds) {
        long startTime = System.currentTimeMillis();
        Map<String, String> scoped = filters == null ? new HashMap<>() : new HashMap<>(filters);
        scoped.put("kbIds", kbIds.stream().map(String::valueOf).collect(Collectors.joining(",")));

        log.info("多库范围检索: query={}, topK={}, kbIds={}", query, topK, kbIds);
        List<SearchResultVO> results = enableHybrid
                ? hybridSearchService.hybridSearch(query, topK, scoped)
                : new ArrayList<>();
        double latency = (System.currentTimeMillis() - startTime) / 1000.0;
        log.info("多库范围检索完成: hits={}, latency={}s", results.size(), latency);
        return SearchResponseVO.builder()
                .results(results)
                .latency(latency)
                .totalHits(results.size())
                .build();
    }

    /**
     * 按 KB 级配置检索：加载 KB 的 vectorWeight/bm25Weight/similarityThreshold 等配置，
     * 覆盖全局默认值。当 kbId 为 null 时退化为全局配置。
     */
    public SearchResponseVO searchWithKbConfig(String query, int topK, boolean enableHybrid,
                                                Map<String, String> filters, Long kbId) {
        long startTime = System.currentTimeMillis();

        Double vectorWeight = null;
        Double bm25Weight = null;
        Double similarityThreshold = null;
        boolean disableRerank = false;
        boolean filterLowScore = false;

        if (kbId != null) {
            KbKnowledgeBase kb = kbMapper.selectById(kbId);
            if (kb != null) {
                vectorWeight = kb.getVectorWeight();
                bm25Weight = kb.getBm25Weight();
                similarityThreshold = kb.getSimilarityThreshold();
                disableRerank = kb.getEnableRerank() != null && kb.getEnableRerank() == 0;
                filterLowScore = kb.getFilterLowScore() != null && kb.getFilterLowScore() == 1;
                log.info("KB级检索配置: kbId={}, vw={}, bw={}", kbId, vectorWeight, bm25Weight);
            }
        }

        List<SearchResultVO> results;
        if (enableHybrid) {
            results = hybridSearchService.hybridSearch(query, topK, filters, vectorWeight, bm25Weight);
        } else {
            results = new ArrayList<>();
        }

        // 低分过滤（KB 级或全局 threshold）
        // 阈值语义是"原始相似度"：向量命中用融合前保留的未加权余弦分（metadata.vectorScore）
        // 比较，避免 vectorWeight(0.7) 把分数压到阈值之下造成误杀；BM25-only 命中回退加权分
        double threshold = similarityThreshold != null ? similarityThreshold
                : ragConfig.getRetrieval().getMultiHopMinScore();
        if (filterLowScore || similarityThreshold != null) {
            final double t = threshold;
            results = results.stream()
                    .filter(r -> {
                        Object raw = r.getMetadata() != null ? r.getMetadata().get("vectorScore") : null;
                        double comparable = raw instanceof Number n ? n.doubleValue() : r.getScore();
                        return comparable >= t;
                    })
                    .collect(Collectors.toList());
        }

        double latency = (System.currentTimeMillis() - startTime) / 1000.0;
        log.info("KB级配置检索完成: kbId={}, hits={}, latency={}s", kbId, results.size(), latency);

        return SearchResponseVO.builder()
                .results(results)
                .latency(latency)
                .totalHits(results.size())
                .build();
    }
}