package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 多跳检索服务
 *
 * 核心职责：实现多轮检索（Multi-Hop Retrieval），通过迭代查询提升复杂问题的召回率。
 *
 * 检索流程：
 *   1. 第1轮：混合检索 → 获取初始结果
 *   2. 重排序：对第1轮结果做语义重排序
 *   3. 高质过滤：筛选分数 >= multiHopMinScore 的高质量结果
 *   4. 查询扩展：从高质量结果中提取关键句/短语，构建第2轮查询
 *   5. 第2轮：用扩展查询再次混合检索 → 合并去重新结果
 *   6. 最终重排序：对合并结果做最终排序，返回 Top-K
 *
 * 适用场景：复杂多面问题、需要多源信息综合回答的场景
 */
@Service
public class MultiHopService {

    private static final Logger log = LoggerFactory.getLogger(MultiHopService.class);

    private final HybridSearchService hybridSearchService;
    private final RerankerService rerankerService;
    private final RagConfig ragConfig;

    public MultiHopService(HybridSearchService hybridSearchService,
                           RerankerService rerankerService,
                           RagConfig ragConfig) {
        this.hybridSearchService = hybridSearchService;
        this.rerankerService = rerankerService;
        this.ragConfig = ragConfig;
    }

    /**
     * 多跳检索主方法：第1轮检索 → 重排序 → 高质量过滤 → 查询扩展 → 第2轮检索 → 合并去重 → 最终排序
     */
    public List<SearchResultVO> multiHopSearch(String query, int topK, Map<String, String> filters) {
        log.info("多轮检索: query={}", query);

        List<SearchResultVO> round1Results = hybridSearchService.hybridSearch(query, topK * 2, filters);

        if (round1Results.isEmpty()) {
            log.info("多轮检索: 第1轮无结果，直接返回空");
            return round1Results;
        }

        round1Results = rerankerService.rerank(
                query, round1Results, ragConfig.getRetrieval().getRerankTopK()
        );

        if (round1Results.isEmpty()) {
            log.info("多轮检索: 重排序后无结果，返回原始结果");
            return round1Results;
        }

        List<SearchResultVO> highQuality = round1Results.stream()
                .filter(r -> r.getScore() >= ragConfig.getRetrieval().getMultiHopMinScore())
                .collect(Collectors.toList());

        int minSources = ragConfig.getRetrieval().getMultiHopMinSources();
        if (highQuality.isEmpty()) {
            log.info("多轮检索: 没有高质量结果（都低于阈值 {})，直接返回第1轮结果，阈值 = {}",
                    ragConfig.getRetrieval().getMultiHopMinScore(), highQuality.size());
            return round1Results.stream().limit(topK).collect(Collectors.toList());
        }

        if (highQuality.size() < minSources) {
            log.info("多轮检索: 高质量结果不足 {}，仍继续扩展查询 (highQuality={})",
                    minSources, highQuality.size());
        } else {
            log.info("多轮检索: 高质量结果数量: {}", highQuality.size());
        }

        // 只要有至少1个高质量结果，就进行第二轮检索，不强制要求 minSources

        String expandedQuery = buildExpandedQuery(query, highQuality);
        log.info("多轮检索: 第2轮查询 = {}", expandedQuery);

        List<SearchResultVO> round2Results = hybridSearchService.hybridSearch(expandedQuery, topK, filters);

        Set<String> seenIds = round1Results.stream()
                .map(SearchResultVO::getId)
                .collect(Collectors.toSet());

        List<SearchResultVO> newResults = round2Results.stream()
                .filter(r -> !seenIds.contains(r.getId()))
                .collect(Collectors.toList());

        List<SearchResultVO> merged = new ArrayList<>(round1Results);
        merged.addAll(newResults);

        merged = rerankerService.rerank(query, merged, topK);

        log.info("多轮检索完成: round1={}, round2={}, merged={}, final={}",
                round1Results.size(), round2Results.size(), merged.size(), Math.min(topK, merged.size()));

        return merged.stream().limit(topK).collect(Collectors.toList());
    }

    private String buildExpandedQuery(String originalQuery, List<SearchResultVO> highQualityResults) {
        // 从高质量结果中提取关键信息，构建扩展查询
        List<String> contextPieces = new ArrayList<>();

        // 收集结果中的关键句子
        for (SearchResultVO result : highQualityResults) {
            String content = result.getContent();
            if (content == null || content.isBlank()) {
                content = result.getParentContent();
            }
            if (content != null && !content.isBlank()) {
                // 提取包含查询关键词的句子
                String[] sentences = content.split("[。！？；\\n]+");
                for (String sentence : sentences) {
                    sentence = sentence.trim();
                    if (sentence.length() > 10 && sentence.length() < 200) {
                        // 检查句子是否包含原始查询中的关键词
                        boolean containsQueryTerm = false;
                        for (String queryTerm : originalQuery.split("[\\s，。、]+")) {
                            if (queryTerm.length() >= 2 && sentence.contains(queryTerm)) {
                                containsQueryTerm = true;
                                break;
                            }
                        }
                        if (containsQueryTerm) {
                            contextPieces.add(sentence);
                            if (contextPieces.size() >= 3) break;
                        }
                    }
                }
            }
        }

        // 构建扩展查询：原始查询 + 相关句子摘要
        StringBuilder sb = new StringBuilder(originalQuery);

        if (!contextPieces.isEmpty()) {
            sb.append(" ");
            // 取相关句子的前 50 个字符作为上下文补充
            sb.append(contextPieces.stream()
                    .map(s -> s.length() > 50 ? s.substring(0, 50) : s)
                    .limit(2)
                    .collect(Collectors.joining(" ")));
        } else {
            // 如果没有找到相关句子，从高质量结果中提取关键短语
            Set<String> keywords = extractKeyPhrases(highQualityResults);
            if (!keywords.isEmpty()) {
                sb.append(" ");
                sb.append(String.join(" ", keywords.stream().limit(3).collect(Collectors.toList())));
            }
        }

        return sb.toString();
    }

    private Set<String> extractKeyPhrases(List<SearchResultVO> results) {
        Set<String> keywords = new HashSet<>();
        for (SearchResultVO result : results) {
            String content = result.getContent();
            if (content == null) {
                content = result.getParentContent();
            }
            if (content != null) {
                // 提取有意义的短语（2-6个中文字符）
                String[] words = content.split("[\\s，。！？；：、\"\"''（）《》\\[\\]【】,.!?;:()]+");
                for (String word : words) {
                    word = word.trim();
                    if (word.length() >= 2 && word.length() <= 12 && !keywords.contains(word)) {
                        keywords.add(word);
                        if (keywords.size() >= 8) {
                            return keywords;
                        }
                    }
                }
            }
        }
        return keywords;
    }
}