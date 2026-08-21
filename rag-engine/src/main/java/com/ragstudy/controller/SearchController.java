package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.SearchRequest;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.service.KnowledgeSearchService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/internal/search")
public class SearchController {

    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

    private final KnowledgeSearchService knowledgeSearchService;

    public SearchController(KnowledgeSearchService knowledgeSearchService) {
        this.knowledgeSearchService = knowledgeSearchService;
    }

    @PostMapping
    public ApiResponse<SearchResponseVO> search(@Valid @RequestBody SearchRequest request) {
        log.info("收到检索请求: query={}, topK={}, hybrid={}",
                request.getQuery(), request.getTopK(), request.isEnableHybrid());

        SearchResponseVO response = knowledgeSearchService.search(
                request.getQuery(),
                request.getTopK(),
                request.isEnableHybrid(),
                request.getFilters()
        );

        return ApiResponse.success(response);
    }

    @PostMapping("/rerank")
    public ApiResponse<SearchResponseVO> searchWithRerank(@Valid @RequestBody SearchRequest request) {
        log.info("收到检索+重排序请求: query={}, topK={}, rerankTopK={}",
                request.getQuery(), request.getTopK(), request.getRerankTopK());

        int rerankTopK = request.getRerankTopK() > 0 ? request.getRerankTopK() : request.getTopK() * 2;

        SearchResponseVO response = knowledgeSearchService.searchWithRerank(
                request.getQuery(),
                request.getTopK(),
                request.isEnableHybrid(),
                request.getFilters(),
                rerankTopK
        );

        return ApiResponse.success(response);
    }

    @PostMapping("/multihop")
    public ApiResponse<SearchResponseVO> multiHopSearch(@Valid @RequestBody SearchRequest request) {
        log.info("收到多轮检索请求: query={}, topK={}", request.getQuery(), request.getTopK());

        SearchResponseVO response = knowledgeSearchService.multiHopSearch(
                request.getQuery(),
                request.getTopK(),
                request.getFilters()
        );

        return ApiResponse.success(response);
    }
}