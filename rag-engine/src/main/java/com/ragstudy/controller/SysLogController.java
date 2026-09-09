package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.service.SysLogService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/system")
public class SysLogController {

    private final SysLogService sysLogService;

    public SysLogController(SysLogService sysLogService) {
        this.sysLogService = sysLogService;
    }

    @GetMapping("/logs")
    public ApiResponse<Map<String, Object>> listLogs(
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String module,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.success(sysLogService.listLogs(level, module, keyword, page, size));
    }

    @GetMapping("/logs/stats")
    public ApiResponse<Map<String, Object>> getLogStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(sysLogService.getLogStats(days));
    }

    @DeleteMapping("/logs/clean")
    public ApiResponse<Map<String, Object>> cleanExpiredLogs(@RequestParam(defaultValue = "90") int days) {
        int count = sysLogService.cleanExpiredLogs(days);
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("cleanedCount", count);
        return ApiResponse.success(result);
    }
}