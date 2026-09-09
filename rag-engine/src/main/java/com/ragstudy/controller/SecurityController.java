package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.AccessControl;
import com.ragstudy.model.entity.RateLimitRule;
import com.ragstudy.model.entity.SensitiveWord;
import com.ragstudy.service.AccessControlService;
import com.ragstudy.service.RateLimitService;
import com.ragstudy.service.SensitiveWordService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/security")
public class SecurityController {

    private final SensitiveWordService sensitiveWordService;
    private final RateLimitService rateLimitService;
    private final AccessControlService accessControlService;

    public SecurityController(SensitiveWordService sensitiveWordService,
                              RateLimitService rateLimitService,
                              AccessControlService accessControlService) {
        this.sensitiveWordService = sensitiveWordService;
        this.rateLimitService = rateLimitService;
        this.accessControlService = accessControlService;
    }

    @GetMapping("/sensitive-words")
    public ApiResponse<IPage<SensitiveWord>> listSensitiveWords(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String kbId) {
        return ApiResponse.success(sensitiveWordService.list(pageNum, pageSize, keyword, category, kbId));
    }

    @PostMapping("/sensitive-words")
    public ApiResponse<SensitiveWord> saveSensitiveWord(@RequestBody SensitiveWord word) {
        return ApiResponse.success(sensitiveWordService.save(word));
    }

    @DeleteMapping("/sensitive-words/{id}")
    public ApiResponse<Void> deleteSensitiveWord(@PathVariable Long id) {
        sensitiveWordService.delete(id);
        return ApiResponse.success();
    }

    @PostMapping("/sensitive-words/batch")
    public ApiResponse<Void> batchImportSensitiveWords(@RequestBody List<SensitiveWord> words) {
        sensitiveWordService.batchImport(words);
        return ApiResponse.success();
    }

    @PostMapping("/sensitive-words/check")
    public ApiResponse<Map<String, Object>> checkSensitiveWords(@RequestBody Map<String, String> body) {
        String text = body.get("text");
        String kbId = body.get("kbId");
        return ApiResponse.success(sensitiveWordService.check(text, kbId));
    }

    @GetMapping("/rate-limits")
    public ApiResponse<IPage<RateLimitRule>> listRateLimits(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return ApiResponse.success(rateLimitService.listRules(pageNum, pageSize));
    }

    @PostMapping("/rate-limits")
    public ApiResponse<RateLimitRule> saveRateLimit(@RequestBody RateLimitRule rule) {
        return ApiResponse.success(rateLimitService.saveRule(rule));
    }

    @DeleteMapping("/rate-limits/{id}")
    public ApiResponse<Void> deleteRateLimit(@PathVariable Long id) {
        rateLimitService.deleteRule(id);
        return ApiResponse.success();
    }

    @GetMapping("/access-controls")
    public ApiResponse<IPage<AccessControl>> listAccessControls(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String ruleType) {
        return ApiResponse.success(accessControlService.list(pageNum, pageSize, ruleType));
    }

    @PostMapping("/access-controls")
    public ApiResponse<AccessControl> saveAccessControl(@RequestBody AccessControl rule) {
        return ApiResponse.success(accessControlService.save(rule));
    }

    @DeleteMapping("/access-controls/{id}")
    public ApiResponse<Void> deleteAccessControl(@PathVariable Long id) {
        accessControlService.delete(id);
        return ApiResponse.success();
    }
}