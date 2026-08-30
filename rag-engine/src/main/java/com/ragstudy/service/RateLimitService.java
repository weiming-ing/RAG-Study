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

/**
 * 限流服务
 *
 * 核心职责：基于令牌桶算法的 API 限流控制。
 *
 * 限流维度：
 *   - targetType: USER / IP / API_KEY / ENDPOINT
 *   - targetValue: 具体的目标值（如用户ID、IP地址）
 *   - limitCount + windowSeconds: 在时间窗口内允许的最大请求数
 *
 * 算法：内存令牌桶（TokenBucket）
 *   - 每个规则独立维护一个桶，以 ConcurrentHashMap 存储
 *   - 桶容量 = limitCount，按 windowSeconds 时间窗口均匀补充
 *   - 请求到达时 tryAcquire()，令牌不足则返回 false（触发限流）
 */
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

    /**
     * 检查限流：遍历所有启用规则，匹配 targetType + targetValue，使用令牌桶判断
     * 任一规则触发限流即返回 false
     */
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

    /**
     * 令牌桶实现：固定容量 + 固定时间窗口补充
     * tryAcquire() 先补充令牌，再尝试消费，保证线程安全
     */
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