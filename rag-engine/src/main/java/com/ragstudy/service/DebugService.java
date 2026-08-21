package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.DebugTestCase;
import com.ragstudy.model.vo.SearchResultVO;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.repository.DebugTestCaseMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class DebugService {

    private final DebugTestCaseMapper testCaseMapper;
    private final KnowledgeSearchService knowledgeSearchService;

    public DebugService(DebugTestCaseMapper testCaseMapper,
                        KnowledgeSearchService knowledgeSearchService) {
        this.testCaseMapper = testCaseMapper;
        this.knowledgeSearchService = knowledgeSearchService;
    }

    public DebugTestCase saveTestCase(DebugTestCase testCase) {
        if (testCase.getId() != null) {
            testCaseMapper.updateById(testCase);
            return testCase;
        }
        testCaseMapper.insert(testCase);
        return testCase;
    }

    public IPage<DebugTestCase> listTestCases(int pageNum, int pageSize, String kbId, String keyword) {
        Page<DebugTestCase> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<DebugTestCase> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(kbId)) {
            wrapper.eq(DebugTestCase::getKbId, kbId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(DebugTestCase::getName, keyword)
                    .or().like(DebugTestCase::getQueryText, keyword)
                    .or().like(DebugTestCase::getTags, keyword));
        }
        wrapper.orderByDesc(DebugTestCase::getCreateTime);

        return testCaseMapper.selectPage(page, wrapper);
    }

    public DebugTestCase getTestCase(Long id) {
        return testCaseMapper.selectById(id);
    }

    public void deleteTestCase(Long id) {
        testCaseMapper.deleteById(id);
    }

    public SearchResponseVO debugSearch(String query, int topK, boolean enableHybrid,
                                         float similarityThreshold, float vectorWeight, float keywordWeight,
                                         Map<String, String> filters) {
        SearchResponseVO response;
        if (enableHybrid) {
            response = knowledgeSearchService.search(query, topK, true, filters);
        } else {
            response = knowledgeSearchService.search(query, topK, false, filters);
        }

        if (response.getResults() != null) {
            response.setResults(response.getResults().stream()
                    .filter(r -> r.getScore() >= similarityThreshold)
                    .limit(topK)
                    .collect(Collectors.toList()));
        }

        return response;
    }

    public Map<String, Object> runAllTestCases(String kbId) {
        LambdaQueryWrapper<DebugTestCase> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(kbId)) {
            wrapper.eq(DebugTestCase::getKbId, kbId);
        }
        List<DebugTestCase> cases = testCaseMapper.selectList(wrapper);

        int total = cases.size();
        int passed = 0;
        List<Map<String, Object>> results = new ArrayList<>();

        for (DebugTestCase tc : cases) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("caseId", tc.getId());
            result.put("caseName", tc.getName());
            result.put("query", tc.getQueryText());

            try {
                SearchResponseVO response = knowledgeSearchService.search(
                        tc.getQueryText(),
                        tc.getTopK() != null ? tc.getTopK() : 5,
                        tc.getEnableHybrid() != null && tc.getEnableHybrid() == 1,
                        new HashMap<>()
                );

                result.put("resultCount", response.getResults() != null ? response.getResults().size() : 0);
                result.put("status", "SUCCESS");

                List<String> matchedDocIds = response.getResults() != null
                        ? response.getResults().stream()
                                .map(r -> r.getMetadata() != null ? (String) r.getMetadata().get("documentId") : null)
                                .filter(Objects::nonNull)
                                .collect(Collectors.toList())
                        : Collections.emptyList();

                boolean casePassed = true;
                if (tc.getExpectedDocIds() != null && !tc.getExpectedDocIds().isBlank()) {
                    List<String> expected = Arrays.asList(tc.getExpectedDocIds().split(","));
                    casePassed = matchedDocIds.containsAll(expected);
                }
                result.put("passed", casePassed);
                if (casePassed) passed++;
            } catch (Exception e) {
                result.put("status", "FAILED");
                result.put("error", e.getMessage());
                result.put("passed", false);
            }

            results.add(result);
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total", total);
        summary.put("passed", passed);
        summary.put("failed", total - passed);
        summary.put("passRate", total > 0 ? String.format("%.1f%%", 100.0 * passed / total) : "N/A");
        summary.put("results", results);
        return summary;
    }
}