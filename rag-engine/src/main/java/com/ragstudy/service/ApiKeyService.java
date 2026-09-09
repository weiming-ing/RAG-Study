package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.ApiKey;
import com.ragstudy.repository.ApiKeyMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.UUID;

@Service
public class ApiKeyService {

    private final ApiKeyMapper apiKeyMapper;
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    public ApiKeyService(ApiKeyMapper apiKeyMapper) {
        this.apiKeyMapper = apiKeyMapper;
    }

    public IPage<ApiKey> list(int pageNum, int pageSize, String keyword, Long userId) {
        Page<ApiKey> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<ApiKey> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(keyword)) {
            wrapper.like(ApiKey::getKeyName, keyword);
        }
        if (userId != null) {
            wrapper.eq(ApiKey::getUserId, userId);
        }
        wrapper.orderByDesc(ApiKey::getCreateTime);
        return apiKeyMapper.selectPage(page, wrapper);
    }

    public ApiKey getById(Long id) {
        return apiKeyMapper.selectById(id);
    }

    public ApiKey generate(Long userId, String keyName, String kbIds, String permissions,
                           Integer rateLimit, Integer dailyLimit, String description, LocalDateTime expireTime) {
        ApiKey apiKey = new ApiKey();
        apiKey.setKeyName(keyName);
        apiKey.setApiKey("ak-" + generateRandomString(32));
        apiKey.setSecretKey("sk-" + UUID.randomUUID().toString().replace("-", ""));
        apiKey.setUserId(userId);
        apiKey.setKbIds(kbIds);
        apiKey.setPermissions(permissions);
        apiKey.setEnabled(1);
        apiKey.setRateLimit(rateLimit != null ? rateLimit : 1000);
        apiKey.setDailyLimit(dailyLimit != null ? dailyLimit : 10000);
        apiKey.setTotalCalls(0L);
        apiKey.setExpireTime(expireTime);
        apiKey.setDescription(description);
        apiKeyMapper.insert(apiKey);
        return apiKey;
    }

    public ApiKey update(Long id, String keyName, Integer enabled, Integer rateLimit,
                         Integer dailyLimit, String description, LocalDateTime expireTime) {
        ApiKey apiKey = apiKeyMapper.selectById(id);
        if (apiKey == null) {
            return null;
        }
        if (keyName != null) apiKey.setKeyName(keyName);
        if (enabled != null) apiKey.setEnabled(enabled);
        if (rateLimit != null) apiKey.setRateLimit(rateLimit);
        if (dailyLimit != null) apiKey.setDailyLimit(dailyLimit);
        if (description != null) apiKey.setDescription(description);
        if (expireTime != null) apiKey.setExpireTime(expireTime);
        apiKeyMapper.updateById(apiKey);
        return apiKey;
    }

    public void delete(Long id) {
        apiKeyMapper.deleteById(id);
    }

    public ApiKey validate(String apiKeyValue) {
        ApiKey apiKey = apiKeyMapper.findByApiKey(apiKeyValue);
        if (apiKey == null) {
            return null;
        }
        if (apiKey.getExpireTime() != null && apiKey.getExpireTime().isBefore(LocalDateTime.now())) {
            return null;
        }
        return apiKey;
    }

    public void recordUsage(String apiKeyValue) {
        apiKeyMapper.incrementCallCount(apiKeyValue);
    }

    private String generateRandomString(int length) {
        byte[] bytes = new byte[length];
        SECURE_RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes).substring(0, length);
    }
}