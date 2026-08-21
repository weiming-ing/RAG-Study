package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.AccessControl;
import com.ragstudy.repository.AccessControlMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class AccessControlService {

    private final AccessControlMapper accessControlMapper;

    public AccessControlService(AccessControlMapper accessControlMapper) {
        this.accessControlMapper = accessControlMapper;
    }

    public IPage<AccessControl> list(int pageNum, int pageSize, String ruleType) {
        Page<AccessControl> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<AccessControl> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(ruleType)) {
            wrapper.eq(AccessControl::getRuleType, ruleType);
        }
        wrapper.orderByDesc(AccessControl::getCreateTime);
        return accessControlMapper.selectPage(page, wrapper);
    }

    public AccessControl save(AccessControl rule) {
        if (rule.getId() != null) {
            accessControlMapper.updateById(rule);
        } else {
            accessControlMapper.insert(rule);
        }
        return rule;
    }

    public void delete(Long id) {
        accessControlMapper.deleteById(id);
    }

    public boolean isBlocked(String ipAddress, Long userId, String apiKey) {
        LocalDateTime now = LocalDateTime.now();

        LambdaQueryWrapper<AccessControl> blacklistWrapper = new LambdaQueryWrapper<>();
        blacklistWrapper.eq(AccessControl::getRuleType, "BLACKLIST")
                .eq(AccessControl::getEnabled, 1)
                .and(w -> {
                    if (ipAddress != null) w.eq(AccessControl::getIpAddress, ipAddress).or();
                    if (userId != null) w.eq(AccessControl::getUserId, userId).or();
                    if (apiKey != null) w.eq(AccessControl::getApiKey, apiKey);
                    return;
                });
        List<AccessControl> blacklist = accessControlMapper.selectList(blacklistWrapper);

        for (AccessControl rule : blacklist) {
            if (rule.getExpireTime() == null || rule.getExpireTime().isAfter(now)) {
                return true;
            }
        }
        return false;
    }

    public boolean isWhitelisted(String ipAddress) {
        LambdaQueryWrapper<AccessControl> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AccessControl::getRuleType, "WHITELIST")
                .eq(AccessControl::getEnabled, 1)
                .eq(AccessControl::getIpAddress, ipAddress);
        return accessControlMapper.selectCount(wrapper) > 0;
    }
}