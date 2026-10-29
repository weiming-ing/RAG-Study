package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.service.SensitiveWordService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 内部安全接口（供 Python 网关调用，走 X-Internal-Token 门禁）
 *
 * 对话链路的敏感词拦截在 Python 侧发起：检索前调用本端点检查用户输入，
 * 命中即拒绝回答。词库与过滤逻辑复用 SensitiveWordService（5 分钟缓存）。
 */
@RestController
@RequestMapping("/api/internal/security")
public class InternalSecurityController {

    private final SensitiveWordService sensitiveWordService;

    public InternalSecurityController(SensitiveWordService sensitiveWordService) {
        this.sensitiveWordService = sensitiveWordService;
    }

    @PostMapping("/sensitive-check")
    public ApiResponse<Map<String, Object>> sensitiveCheck(@RequestBody Map<String, String> body) {
        String text = body.getOrDefault("text", "");
        String kbId = body.get("kbId");
        if (text.isBlank()) {
            return ApiResponse.success(Map.of("hasSensitive", false, "matchedWords", java.util.List.of(), "matchCount", 0));
        }
        return ApiResponse.success(sensitiveWordService.check(text, kbId));
    }
}
