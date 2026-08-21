package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class HybridSearchService {

    private static final Logger log = LoggerFactory.getLogger(HybridSearchService.class);

    private final RagConfig ragConfig;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final EmbeddingService embeddingService;

    public HybridSearchService(RagConfig ragConfig, VectorStoreService vectorStoreService,
                               Bm25Service bm25Service, EmbeddingService embeddingService) {
        this.ragConfig = ragConfig;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.embeddingService = embeddingService;
    }

    public List<SearchResultVO> hybridSearch(String query, int topK, Map<String, String> filters) {
        List<SearchResultVO> vectorResults;
        List<SearchResultVO> bm25Results;

        try {
            float[] queryVector = embeddingService.embed(query);
            vectorResults = vectorStoreService.search(
                    ragConfig.getQdrant().getCollectionName(),
                    queryVector,
                    topK * 2,
                    filters
            );
        } catch (Exception e) {
            log.error("向量检索失败", e);
            vectorResults = List.of();
        }

        try {
            bm25Results = bm25Service.search(query, topK * 2);
        } catch (Exception e) {
            log.error("BM25 检索失败", e);
            bm25Results = List.of();
        }

        List<SearchResultVO> merged = mergeResults(vectorResults, bm25Results);
        List<SearchResultVO> deduplicated = deduplicate(merged);

        return deduplicated.stream()
                .limit(topK)
                .collect(Collectors.toList());
    }

    private List<SearchResultVO> mergeResults(List<SearchResultVO> vectorResults, List<SearchResultVO> bm25Results) {
        double vectorWeight = ragConfig.getRetrieval().getVectorWeight();
        double bm25Weight = ragConfig.getRetrieval().getBm25Weight();

        Map<String, SearchResultVO> merged = new LinkedHashMap<>();

        for (SearchResultVO r : vectorResults) {
            SearchResultVO weighted = SearchResultVO.builder()
                    .id(r.getId())
                    .content(r.getContent())
                    .parentContent(r.getParentContent())
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
                        .content(r.getContent())
                        .parentContent(r.getParentContent())
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
}