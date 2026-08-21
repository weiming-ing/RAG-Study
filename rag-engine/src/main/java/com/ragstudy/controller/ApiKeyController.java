package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.ApiKey;
import com.ragstudy.service.ApiKeyService;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

@RestController
@RequestMapping("/api/api-keys")
public class ApiKeyController {

    private final ApiKeyService apiKeyService;

    public ApiKeyController(ApiKeyService apiKeyService) {
        this.apiKeyService = apiKeyService;
    }

    @GetMapping
    public ApiResponse<IPage<ApiKey>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Long userId) {
        return ApiResponse.success(apiKeyService.list(pageNum, pageSize, keyword, userId));
    }

    @GetMapping("/{id}")
    public ApiResponse<ApiKey> getById(@PathVariable Long id) {
        return ApiResponse.success(apiKeyService.getById(id));
    }

    @PostMapping
    public ApiResponse<ApiKey> generate(@RequestBody Map<String, Object> body) {
        Long userId = body.get("userId") != null ? Long.valueOf(body.get("userId").toString()) : null;
        String keyName = (String) body.get("keyName");
        String kbIds = body.get("kbIds") != null ? body.get("kbIds").toString() : null;
        String permissions = body.get("permissions") != null ? body.get("permissions").toString() : null;
        Integer rateLimit = body.get("rateLimit") != null ? Integer.valueOf(body.get("rateLimit").toString()) : null;
        Integer dailyLimit = body.get("dailyLimit") != null ? Integer.valueOf(body.get("dailyLimit").toString()) : null;
        String description = (String) body.get("description");
        LocalDateTime expireTime = body.get("expireTime") != null ?
                LocalDateTime.parse(body.get("expireTime").toString().replace(" ", "T")) : null;

        return ApiResponse.success(apiKeyService.generate(userId, keyName, kbIds, permissions,
                rateLimit, dailyLimit, description, expireTime));
    }

    @PutMapping("/{id}")
    public ApiResponse<ApiKey> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        String keyName = (String) body.get("keyName");
        Integer enabled = body.get("enabled") != null ? Integer.valueOf(body.get("enabled").toString()) : null;
        Integer rateLimit = body.get("rateLimit") != null ? Integer.valueOf(body.get("rateLimit").toString()) : null;
        Integer dailyLimit = body.get("dailyLimit") != null ? Integer.valueOf(body.get("dailyLimit").toString()) : null;
        String description = (String) body.get("description");
        LocalDateTime expireTime = body.get("expireTime") != null ?
                LocalDateTime.parse(body.get("expireTime").toString().replace(" ", "T")) : null;

        return ApiResponse.success(apiKeyService.update(id, keyName, enabled, rateLimit, dailyLimit, description, expireTime));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        apiKeyService.delete(id);
        return ApiResponse.success();
    }
}