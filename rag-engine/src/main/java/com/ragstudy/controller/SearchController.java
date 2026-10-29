package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.SearchRequest;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.service.EmbeddingService;
import com.ragstudy.service.KnowledgeSearchService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/internal/search")
public class SearchController {

    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

    private final KnowledgeSearchService knowledgeSearchService;
    private final EmbeddingService embeddingService;

    public SearchController(KnowledgeSearchService knowledgeSearchService, EmbeddingService embeddingService) {
        this.knowledgeSearchService = knowledgeSearchService;
        this.embeddingService = embeddingService;
    }

    @PostMapping
    public ApiResponse<SearchResponseVO> search(@Valid @RequestBody SearchRequest request) {
        log.info("收到检索请求: query={}, topK={}, hybrid={}, kbId={}",
                request.getQuery(), request.getTopK(), request.isEnableHybrid(), request.getKbId());

        SearchResponseVO response;
        if (request.getKbIds() != null && !request.getKbIds().isEmpty()) {
            // 多知识库范围（服务端授权解析结果）；多 KB 不套用单一 KB 检索配置
            response = knowledgeSearchService.searchInKbs(
                    request.getQuery(), request.getTopK(), request.isEnableHybrid(),
                    request.getFilters(), request.getKbIds());
        } else if (request.getKbId() != null) {
            response = knowledgeSearchService.searchWithKbConfig(
                    request.getQuery(), request.getTopK(), request.isEnableHybrid(),
                    request.getFilters(), request.getKbId());
        } else {
            response = knowledgeSearchService.search(
                    request.getQuery(), request.getTopK(), request.isEnableHybrid(),
                    request.getFilters());
        }

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

    /**
     * 获取文本的 Embedding 向量（供 Python 语义缓存使用）
     * POST /api/internal/search/embed
     * Body: {"text": "查询文本"}
     * Response: {"code": 0, "data": {"text": "...", "vector": [0.1, 0.2, ...], "dimension": 512}}
     */
    @PostMapping("/embed")
    public ApiResponse<Map<String, Object>> embed(@RequestBody Map<String, String> body) {
        String text = body.get("text");
        if (text == null || text.isBlank()) {
            return ApiResponse.error(400, "text 参数不能为空");
        }
        try {
            float[] vector = embeddingService.embed(text);
            Map<String, Object> result = Map.of(
                    "text", text,
                    "vector", vector,
                    "dimension", embeddingService.getDimension()
            );
            return ApiResponse.success(result);
        } catch (Exception e) {
            log.error("Embedding 失败: text={}", text, e);
            return ApiResponse.error(500, "Embedding 失败: " + e.getMessage());
        }
    }
}