package com.ragstudy.service;

import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class RerankerService {

    private static final Logger log = LoggerFactory.getLogger(RerankerService.class);

    private final EmbeddingService embeddingService;

    public RerankerService(EmbeddingService embeddingService) {
        this.embeddingService = embeddingService;
    }

    public List<SearchResultVO> rerank(String query, List<SearchResultVO> candidates, int topK) {
        if (candidates == null || candidates.isEmpty()) {
            return List.of();
        }

        log.info("重排序: query={}, candidates={}, topK={}", query, candidates.size(), topK);

        float[] queryVector = embeddingService.embed(query);

        List<ScoredCandidate> scored = new ArrayList<>();
        for (SearchResultVO candidate : candidates) {
            String content = getContent(candidate);
            if (content == null || content.isBlank()) {
                continue;
            }

            float[] contentVector = embeddingService.embed(content);
            float similarity = cosineSimilarity(queryVector, contentVector);

            ScoredCandidate sc = new ScoredCandidate();
            sc.result = candidate;
            sc.similarity = similarity;
            sc.combinedScore = 0.6 * similarity + 0.4 * candidate.getScore();
            scored.add(sc);
        }

        scored.sort((a, b) -> Double.compare(b.combinedScore, a.combinedScore));

        List<SearchResultVO> reranked = new ArrayList<>();
        for (int i = 0; i < Math.min(topK, scored.size()); i++) {
            SearchResultVO result = scored.get(i).result;
            SearchResultVO updated = SearchResultVO.builder()
                    .id(result.getId())
                    .chunkId(result.getChunkId())
                    .content(result.getContent())
                    .parentContent(result.getParentContent())
                    .parentChunkId(result.getParentChunkId())
                    .score(scored.get(i).combinedScore)
                    .metadata(result.getMetadata() != null ? new HashMap<>(result.getMetadata()) : new HashMap<>())
                    .build();
            reranked.add(updated);
        }

        log.info("重排序完成: topK={}, scores=[{}]",
                reranked.size(),
                reranked.stream().map(r -> String.format("%.4f", r.getScore())).reduce((a, b) -> a + ", " + b).orElse(""));
        return reranked;
    }

    private String getContent(SearchResultVO result) {
        if (result.getContent() != null && !result.getContent().isBlank()) {
            return result.getContent();
        }
        if (result.getParentContent() != null && !result.getParentContent().isBlank()) {
            return result.getParentContent();
        }
        return null;
    }

    private float cosineSimilarity(float[] a, float[] b) {
        if (a.length != b.length) {
            return 0f;
        }
        float dot = 0f, normA = 0f, normB = 0f;
        for (int i = 0; i < a.length; i++) {
            dot += a[i] * b[i];
            normA += a[i] * a[i];
            normB += b[i] * b[i];
        }
        float denom = (float) (Math.sqrt(normA) * Math.sqrt(normB));
        return denom > 0 ? dot / denom : 0f;
    }

    private static class ScoredCandidate {
        SearchResultVO result;
        float similarity;
        double combinedScore;
    }
}