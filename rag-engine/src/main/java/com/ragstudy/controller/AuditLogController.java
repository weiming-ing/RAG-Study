package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.AuditLog;
import com.ragstudy.service.AuditLogService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/audit-logs")
public class AuditLogController {

    private static final Logger log = LoggerFactory.getLogger(AuditLogController.class);

    private final AuditLogService auditLogService;

    public AuditLogController(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @GetMapping
    public ApiResponse<IPage<AuditLog>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String operation,
            @RequestParam(required = false) String targetType,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String result,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate) {
        return ApiResponse.success(auditLogService.list(
                pageNum, pageSize, operation, targetType, keyword, userId, result, startDate, endDate));
    }

    @GetMapping("/{id}")
    public ApiResponse<AuditLog> getById(@PathVariable Long id) {
        AuditLog auditLog = auditLogService.getById(id);
        if (auditLog == null) {
            return ApiResponse.error(404, "审计日志不存在");
        }
        return ApiResponse.success(auditLog);
    }

    @GetMapping("/stats/operations")
    public ApiResponse<?> getOperationStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(auditLogService.getOperationStats(days));
    }

    @GetMapping("/stats/daily")
    public ApiResponse<?> getDailyStats(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(auditLogService.getDailyStats(days));
    }

    @PostMapping
    public ApiResponse<Void> create(@RequestBody AuditLog auditLog) {
        auditLogService.log(
            auditLog.getUserId(),
            auditLog.getUsername(),
            auditLog.getOperation(),
            auditLog.getTargetType(),
            auditLog.getTargetId(),
            auditLog.getTargetName(),
            auditLog.getDetail(),
            auditLog.getResult()
        );
        return ApiResponse.success();
    }
}