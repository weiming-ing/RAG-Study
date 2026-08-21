package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.SystemAlert;
import com.ragstudy.service.DashboardService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping("/overview")
    public ApiResponse<Map<String, Object>> overview() {
        return ApiResponse.success(dashboardService.getDashboardOverview());
    }

    @GetMapping("/api-stats")
    public ApiResponse<Map<String, Object>> apiStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(dashboardService.getApiCallStats(days));
    }

    @GetMapping("/token-stats")
    public ApiResponse<Map<String, Object>> tokenStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(dashboardService.getTokenUsageStats(days));
    }

    @GetMapping("/hot-docs")
    public ApiResponse<?> hotDocs(@RequestParam(defaultValue = "7") int days,
                                  @RequestParam(defaultValue = "20") int limit) {
        return ApiResponse.success(dashboardService.getTopHotDocs(days, limit));
    }

    @GetMapping("/kb-hot-rank")
    public ApiResponse<?> kbHotRank(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(dashboardService.getKbHotRank(days));
    }

    @GetMapping("/task-stats")
    public ApiResponse<Map<String, Object>> taskStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(dashboardService.getTaskStats(days));
    }

    @GetMapping("/alerts")
    public ApiResponse<?> alerts() {
        return ApiResponse.success(dashboardService.getActiveAlerts());
    }

    @PutMapping("/alerts/{id}/resolve")
    public ApiResponse<Void> resolveAlert(@PathVariable Long id) {
        dashboardService.resolveAlert(id);
        return ApiResponse.success();
    }

    // ========== 数据记录接口（供 Python 后端调用） ==========

    @PostMapping("/record/api-call")
    public ApiResponse<Void> recordApiCall(@RequestBody Map<String, Object> body) {
        String kbId = (String) body.getOrDefault("kbId", "");
        String apiPath = (String) body.getOrDefault("apiPath", "/api/chat");
        boolean success = (boolean) body.getOrDefault("success", true);
        double latencyMs = body.get("latencyMs") != null ? ((Number) body.get("latencyMs")).doubleValue() : 0;
        dashboardService.recordApiCall(kbId, apiPath, success, latencyMs);
        return ApiResponse.success();
    }

    @PostMapping("/record/doc-hit")
    public ApiResponse<Void> recordDocHit(@RequestBody Map<String, Object> body) {
        String documentId = (String) body.getOrDefault("documentId", "unknown");
        String docName = (String) body.getOrDefault("docName", "未知文档");
        String kbId = (String) body.getOrDefault("kbId", "");
        dashboardService.recordDocHit(documentId, docName, kbId);
        return ApiResponse.success();
    }

    @PostMapping("/record/token-usage")
    public ApiResponse<Void> recordTokenUsage(@RequestBody Map<String, Object> body) {
        String kbId = (String) body.getOrDefault("kbId", "");
        Long userId = body.get("userId") != null ? ((Number) body.get("userId")).longValue() : null;
        Long promptTokens = body.get("promptTokens") != null ? ((Number) body.get("promptTokens")).longValue() : 0L;
        Long completionTokens = body.get("completionTokens") != null ? ((Number) body.get("completionTokens")).longValue() : 0L;
        dashboardService.recordTokenUsage(kbId, userId, promptTokens, completionTokens);
        return ApiResponse.success();
    }
}