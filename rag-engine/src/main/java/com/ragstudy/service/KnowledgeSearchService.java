package com.ragstudy.service;

import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class KnowledgeSearchService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeSearchService.class);

    private final HybridSearchService hybridSearchService;
    private final RerankerService rerankerService;
    private final MultiHopService multiHopService;

    public KnowledgeSearchService(HybridSearchService hybridSearchService,
                                  RerankerService rerankerService,
                                  MultiHopService multiHopService) {
        this.hybridSearchService = hybridSearchService;
        this.rerankerService = rerankerService;
        this.multiHopService = multiHopService;
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
}