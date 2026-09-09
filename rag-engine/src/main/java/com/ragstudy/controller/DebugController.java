package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.DebugTestCase;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.service.DebugService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/debug")
public class DebugController {

    private static final Logger log = LoggerFactory.getLogger(DebugController.class);

    private final DebugService debugService;

    public DebugController(DebugService debugService) {
        this.debugService = debugService;
    }

    @PostMapping("/search")
    public ApiResponse<SearchResponseVO> debugSearch(@RequestBody Map<String, Object> body) {
        String query = (String) body.get("query");
        int topK = body.get("topK") != null ? ((Number) body.get("topK")).intValue() : 5;
        boolean enableHybrid = body.get("enableHybrid") == null || (Boolean) body.get("enableHybrid");
        float similarityThreshold = body.get("similarityThreshold") != null
                ? ((Number) body.get("similarityThreshold")).floatValue() : 0.0f;
        float vectorWeight = body.get("vectorWeight") != null
                ? ((Number) body.get("vectorWeight")).floatValue() : 0.7f;
        float keywordWeight = body.get("keywordWeight") != null
                ? ((Number) body.get("keywordWeight")).floatValue() : 0.3f;

        @SuppressWarnings("unchecked")
        Map<String, String> filters = (Map<String, String>) body.get("filters");

        log.info("检索调试: query={}, topK={}, hybrid={}, threshold={}, vw={}, kw={}",
                query, topK, enableHybrid, similarityThreshold, vectorWeight, keywordWeight);

        SearchResponseVO response = debugService.debugSearch(
                query, topK, enableHybrid,
                similarityThreshold, vectorWeight, keywordWeight,
                filters
        );
        return ApiResponse.success(response);
    }

    @GetMapping("/test-cases")
    public ApiResponse<IPage<DebugTestCase>> listTestCases(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String kbId,
            @RequestParam(required = false) String keyword) {
        return ApiResponse.success(debugService.listTestCases(pageNum, pageSize, kbId, keyword));
    }

    @GetMapping("/test-cases/{id}")
    public ApiResponse<DebugTestCase> getTestCase(@PathVariable Long id) {
        DebugTestCase tc = debugService.getTestCase(id);
        if (tc == null) {
            return ApiResponse.error(404, "测试案例不存在");
        }
        return ApiResponse.success(tc);
    }

    @PostMapping("/test-cases")
    public ApiResponse<DebugTestCase> saveTestCase(@Valid @RequestBody DebugTestCase testCase) {
        return ApiResponse.success(debugService.saveTestCase(testCase));
    }

    @PutMapping("/test-cases/{id}")
    public ApiResponse<DebugTestCase> updateTestCase(@PathVariable Long id, @RequestBody DebugTestCase testCase) {
        testCase.setId(id);
        return ApiResponse.success(debugService.saveTestCase(testCase));
    }

    @DeleteMapping("/test-cases/{id}")
    public ApiResponse<Void> deleteTestCase(@PathVariable Long id) {
        debugService.deleteTestCase(id);
        return ApiResponse.success();
    }

    @PostMapping("/test-cases/run-all")
    public ApiResponse<Map<String, Object>> runAllTestCases(@RequestBody Map<String, String> body) {
        String kbId = body.getOrDefault("kbId", null);
        return ApiResponse.success(debugService.runAllTestCases(kbId));
    }
}