package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.AuditLog;
import com.ragstudy.repository.AuditLogMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class AuditLogService {

    private static final Logger log = LoggerFactory.getLogger(AuditLogService.class);

    private final AuditLogMapper auditLogMapper;

    public AuditLogService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    @Async
    public void log(Long userId, String username, String operation, String targetType,
                    String targetId, String targetName, String detail, String result) {
        try {
            AuditLog auditLog = new AuditLog();
            auditLog.setUserId(userId);
            auditLog.setUsername(username);
            auditLog.setOperation(operation);
            auditLog.setTargetType(targetType);
            auditLog.setTargetId(targetId);
            auditLog.setTargetName(targetName);
            // 在详情前自动带上唯一标识占位（插入后回填）
            auditLog.setDetail(detail);
            auditLog.setResult(result != null ? result : "SUCCESS");
            auditLog.setCreateTime(LocalDateTime.now());
            auditLogMapper.insert(auditLog);

            // 插入后回填 uniqueTag
            String uniqueTag = formatLogUniqueId(auditLog.getId(), auditLog.getCreateTime());
            auditLog.setUniqueTag(uniqueTag);
            // 更新详情，在开头加上唯一标识
            String updatedDetail = "[" + uniqueTag + "] " + (detail != null ? detail : "");
            auditLog.setDetail(updatedDetail);
            auditLogMapper.updateById(auditLog);
        } catch (Exception e) {
            log.error("审计日志写入失败: operation={}", operation, e);
        }
    }

    /**
     * 生成带唯一标识的审计日志详情前缀
     * 格式: LOG-YYYYMMDD-000001 基于 ID 和创建时间生成
     */
    public static String formatLogUniqueId(long id, LocalDateTime createTime) {
        String datePart = String.format("%d%02d%02d",
                createTime.getYear(),
                createTime.getMonthValue(),
                createTime.getDayOfMonth());
        return String.format("LOG-%s-%06d", datePart, id);
    }

    /**
     * 从格式化字符串中提取唯一标识，如果已存在于详情开头
     */
    public static String extractUniqueIdFromDetail(String detail) {
        if (detail == null || !detail.startsWith("LOG-")) return null;
        int firstSpace = detail.indexOf(' ');
        if (firstSpace > 0) {
            return detail.substring(0, firstSpace);
        }
        return detail.length() > 20 ? detail.substring(0, 20) : detail;
    }

    public IPage<AuditLog> list(int pageNum, int pageSize, String operation, String targetType,
                                 String keyword, Long userId, String result, String startDate, String endDate) {
        Page<AuditLog> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<AuditLog> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(operation)) {
            wrapper.eq(AuditLog::getOperation, operation);
        }
        if (StringUtils.hasText(targetType)) {
            wrapper.eq(AuditLog::getTargetType, targetType);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(AuditLog::getTargetName, keyword)
                    .or().like(AuditLog::getDetail, keyword));
        }
        if (userId != null) {
            wrapper.eq(AuditLog::getUserId, userId);
        }
        if (StringUtils.hasText(result)) {
            wrapper.eq(AuditLog::getResult, result);
        }
        if (StringUtils.hasText(startDate)) {
            wrapper.ge(AuditLog::getCreateTime, startDate + " 00:00:00");
        }
        if (StringUtils.hasText(endDate)) {
            wrapper.le(AuditLog::getCreateTime, endDate + " 23:59:59");
        }
        wrapper.orderByDesc(AuditLog::getCreateTime);

        IPage<AuditLog> pageResult = auditLogMapper.selectPage(page, wrapper);
        // 为每条日志填充唯一标识 uniqueTag
        for (AuditLog log : pageResult.getRecords()) {
            if (log.getCreateTime() != null) {
                log.setUniqueTag(AuditLogService.formatLogUniqueId(log.getId(), log.getCreateTime()));
            }
        }
        return pageResult;
    }

    public AuditLog getById(Long id) {
        AuditLog auditLog = auditLogMapper.selectById(id);
        if (auditLog != null && auditLog.getCreateTime() != null) {
            auditLog.setUniqueTag(formatLogUniqueId(auditLog.getId(), auditLog.getCreateTime()));
        }
        return auditLog;
    }

    public List<Map<String, Object>> getOperationStats(int days) {
        return auditLogMapper.countByOperation(days);
    }

    public List<Map<String, Object>> getDailyStats(int days) {
        return auditLogMapper.countByDay(days);
    }

    public long count() {
        return auditLogMapper.selectCount(null);
    }
}