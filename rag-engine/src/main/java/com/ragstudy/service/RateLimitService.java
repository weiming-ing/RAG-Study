package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.RateLimitRule;
import com.ragstudy.repository.RateLimitRuleMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class RateLimitService {

    private final RateLimitRuleMapper ruleMapper;
    private final Map<String, TokenBucket> buckets = new ConcurrentHashMap<>();

    public RateLimitService(RateLimitRuleMapper ruleMapper) {
        this.ruleMapper = ruleMapper;
    }

    public IPage<RateLimitRule> listRules(int pageNum, int pageSize) {
        Page<RateLimitRule> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<RateLimitRule> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(RateLimitRule::getCreateTime);
        return ruleMapper.selectPage(page, wrapper);
    }

    public RateLimitRule saveRule(RateLimitRule rule) {
        if (rule.getId() != null) {
            ruleMapper.updateById(rule);
        } else {
            ruleMapper.insert(rule);
        }
        return rule;
    }

    public void deleteRule(Long id) {
        ruleMapper.deleteById(id);
    }

    public boolean checkLimit(String targetType, String targetValue, String apiPath) {
        LambdaQueryWrapper<RateLimitRule> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(RateLimitRule::getTargetType, targetType)
                .eq(RateLimitRule::getEnabled, 1);
        List<RateLimitRule> rules = ruleMapper.selectList(wrapper);

        for (RateLimitRule rule : rules) {
            if (rule.getTargetValue() != null && !rule.getTargetValue().equals(targetValue)) {
                continue;
            }
            String bucketKey = rule.getId() + ":" + targetValue;
            TokenBucket bucket = buckets.computeIfAbsent(bucketKey,
                    k -> new TokenBucket(rule.getLimitCount(), rule.getWindowSeconds()));
            if (!bucket.tryAcquire()) {
                return false;
            }
        }
        return true;
    }

    private static class TokenBucket {
        private final int capacity;
        private final int windowSeconds;
        private int tokens;
        private long lastRefillTime;

        TokenBucket(int capacity, int windowSeconds) {
            this.capacity = capacity;
            this.windowSeconds = windowSeconds;
            this.tokens = capacity;
            this.lastRefillTime = System.currentTimeMillis();
        }

        synchronized boolean tryAcquire() {
            refill();
            if (tokens > 0) {
                tokens--;
                return true;
            }
            return false;
        }

        private void refill() {
            long now = System.currentTimeMillis();
            long elapsed = now - lastRefillTime;
            int refillTokens = (int) (elapsed / 1000.0 / windowSeconds * capacity);
            if (refillTokens > 0) {
                tokens = Math.min(capacity, tokens + refillTokens);
                lastRefillTime = now;
            }
        }
    }
}