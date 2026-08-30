package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ragstudy.model.entity.*;
import com.ragstudy.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 仪表盘统计服务
 *
 * 核心职责：管理后台仪表盘的数据聚合与统计。
 *
 * 统计维度：
 *   - 概览：文档数、切片数、知识库数、用户数、活跃告警数
 *   - API 调用：接口调用趋势、热门接口排行
 *   - Token 用量：每日 Token 消耗趋势、知识库消耗排行
 *   - 文档热度：热门文档排行、知识库热度排行
 *   - 任务监控：解析任务状态统计、任务类型分布
 *   - 系统告警：活跃告警列表、告警解决
 *
 * 异步记录：recordApiCall / recordDocHit / recordTokenUsage 使用 @Async 异步写入统计表
 */
@Service
public class DashboardService {

    private static final Logger log = LoggerFactory.getLogger(DashboardService.class);

    private final DashboardStatMapper dashboardStatMapper;
    private final ApiCallStatMapper apiCallStatMapper;
    private final TokenUsageStatMapper tokenUsageStatMapper;
    private final DocHotStatMapper docHotStatMapper;
    private final TaskMonitorMapper taskMonitorMapper;
    private final SystemAlertMapper systemAlertMapper;
    private final KnowledgeDocumentMapper documentMapper;
    private final KnowledgeChunkMapper chunkMapper;
    private final KbKnowledgeBaseMapper kbMapper;
    private final ConversationLogMapper conversationLogMapper;
    private final SysUserMapper userMapper;

    public DashboardService(DashboardStatMapper dashboardStatMapper,
                            ApiCallStatMapper apiCallStatMapper,
                            TokenUsageStatMapper tokenUsageStatMapper,
                            DocHotStatMapper docHotStatMapper,
                            TaskMonitorMapper taskMonitorMapper,
                            SystemAlertMapper systemAlertMapper,
                            KnowledgeDocumentMapper documentMapper,
                            KnowledgeChunkMapper chunkMapper,
                            KbKnowledgeBaseMapper kbMapper,
                            ConversationLogMapper conversationLogMapper,
                            SysUserMapper userMapper) {
        this.dashboardStatMapper = dashboardStatMapper;
        this.apiCallStatMapper = apiCallStatMapper;
        this.tokenUsageStatMapper = tokenUsageStatMapper;
        this.docHotStatMapper = docHotStatMapper;
        this.taskMonitorMapper = taskMonitorMapper;
        this.systemAlertMapper = systemAlertMapper;
        this.documentMapper = documentMapper;
        this.chunkMapper = chunkMapper;
        this.kbMapper = kbMapper;
        this.conversationLogMapper = conversationLogMapper;
        this.userMapper = userMapper;
    }

    public Map<String, Object> getDashboardOverview() {
        Map<String, Object> overview = new LinkedHashMap<>();

        Long kbCount = kbMapper.selectCount(null);
        Long docCount = documentMapper.selectCount(null);
        Long chunkCount = chunkMapper.selectCount(null);
        Long questionCount = conversationLogMapper.selectCount(null);
        Long userCount = userMapper.selectCount(null);

        overview.put("totalKbCount", kbCount);
        overview.put("totalDocCount", docCount);
        overview.put("totalChunkCount", chunkCount);
        overview.put("totalQuestionCount", questionCount);
        overview.put("totalUserCount", userCount);

        Long activeAlertCount = systemAlertMapper.countActiveRecent(7);
        overview.put("activeAlertCount", activeAlertCount);

        return overview;
    }

    public Map<String, Object> getApiCallStats(int days) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("topApiPaths", apiCallStatMapper.topApiPaths(days));
        stats.put("dailyTrend", apiCallStatMapper.dailyCallTrend(days));
        return stats;
    }

    public Map<String, Object> getTokenUsageStats(int days) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("dailyTrend", tokenUsageStatMapper.dailyTokenTrend(days));
        stats.put("topKb", tokenUsageStatMapper.topKbByToken(days, 10));
        return stats;
    }

    public List<Map<String, Object>> getTopHotDocs(int days, int limit) {
        return docHotStatMapper.topHotDocs(days, limit);
    }

    public List<Map<String, Object>> getKbHotRank(int days) {
        return docHotStatMapper.kbHotRank(days);
    }

    public Map<String, Object> getTaskStats(int days) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("statusCount", taskMonitorMapper.countByStatus(days));
        stats.put("typeStats", taskMonitorMapper.taskTypeStats(days));
        return stats;
    }

    public List<SystemAlert> getActiveAlerts() {
        LambdaQueryWrapper<SystemAlert> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SystemAlert::getStatus, "ACTIVE")
                .orderByDesc(SystemAlert::getCreateTime);
        return systemAlertMapper.selectList(wrapper);
    }

    public void resolveAlert(Long alertId) {
        SystemAlert alert = systemAlertMapper.selectById(alertId);
        if (alert != null) {
            alert.setStatus("RESOLVED");
            alert.setResolvedTime(LocalDateTime.now());
            systemAlertMapper.updateById(alert);
        }
    }

    @Async
    public void createAlert(String alertType, String alertLevel, String title, String detail, String source) {
        try {
            SystemAlert alert = new SystemAlert();
            alert.setAlertType(alertType);
            alert.setAlertLevel(alertLevel);
            alert.setTitle(title);
            alert.setDetail(detail);
            alert.setSource(source);
            alert.setStatus("ACTIVE");
            systemAlertMapper.insert(alert);
            log.warn("系统告警: [{}] {} - {}", alertLevel, title, detail);
        } catch (Exception e) {
            log.error("告警创建失败", e);
        }
    }

    /**
     * 异步记录 API 调用统计（从请求上下文提取 apiPath/kbId/userId）
     */
    @Async
    public void recordApiCall(String kbId, String apiPath, boolean success, double latencyMs) {
        try {
            LocalDate today = LocalDate.now();
            LambdaQueryWrapper<ApiCallStat> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(ApiCallStat::getKbId, kbId)
                    .eq(ApiCallStat::getApiPath, apiPath)
                    .eq(ApiCallStat::getStatDate, today);
            ApiCallStat stat = apiCallStatMapper.selectOne(wrapper);

            if (stat == null) {
                stat = new ApiCallStat();
                stat.setKbId(kbId);
                stat.setApiPath(apiPath);
                stat.setStatDate(today);
                stat.setCallCount(1L);
                stat.setSuccessCount(success ? 1L : 0L);
                stat.setFailCount(success ? 0L : 1L);
                stat.setAvgLatencyMs(latencyMs);
                apiCallStatMapper.insert(stat);
            } else {
                stat.setCallCount(stat.getCallCount() + 1);
                if (success) {
                    stat.setSuccessCount(stat.getSuccessCount() + 1);
                } else {
                    stat.setFailCount(stat.getFailCount() + 1);
                }
                stat.setAvgLatencyMs((stat.getAvgLatencyMs() * (stat.getCallCount() - 1) + latencyMs) / stat.getCallCount());
                apiCallStatMapper.updateById(stat);
            }
        } catch (Exception e) {
            log.error("API调用统计记录失败", e);
        }
    }

    /**
     * 异步记录文档热度统计（检索命中时调用，记录引用次数）
     */
    @Async
    public void recordDocHit(String documentId, String docName, String kbId) {
        try {
            LocalDate today = LocalDate.now();
            LambdaQueryWrapper<DocHotStat> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(DocHotStat::getDocumentId, documentId)
                    .eq(DocHotStat::getStatDate, today);
            DocHotStat stat = docHotStatMapper.selectOne(wrapper);

            if (stat == null) {
                stat = new DocHotStat();
                stat.setDocumentId(documentId);
                stat.setDocName(docName);
                stat.setKbId(kbId);
                stat.setStatDate(today);
                stat.setHitCount(1L);
                stat.setSearchCount(1L);
                docHotStatMapper.insert(stat);
            } else {
                stat.setHitCount(stat.getHitCount() + 1);
                stat.setSearchCount(stat.getSearchCount() + 1);
                docHotStatMapper.updateById(stat);
            }
        } catch (Exception e) {
            log.error("文档热度统计记录失败", e);
        }
    }

    /**
     * 异步记录 Token 用量统计（LLM 调用完成后，记录 prompt + completion tokens）
     */
    @Async
    public void recordTokenUsage(String kbId, Long userId, Long promptTokens, Long completionTokens) {
        try {
            LocalDate today = LocalDate.now();
            LambdaQueryWrapper<TokenUsageStat> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(TokenUsageStat::getKbId, kbId)
                    .eq(TokenUsageStat::getUserId, userId)
                    .eq(TokenUsageStat::getStatDate, today);
            TokenUsageStat stat = tokenUsageStatMapper.selectOne(wrapper);

            if (stat == null) {
                stat = new TokenUsageStat();
                stat.setKbId(kbId);
                stat.setUserId(userId);
                stat.setStatDate(today);
                stat.setPromptTokens(promptTokens != null ? promptTokens : 0L);
                stat.setCompletionTokens(completionTokens != null ? completionTokens : 0L);
                stat.setTotalTokens((promptTokens != null ? promptTokens : 0L) + (completionTokens != null ? completionTokens : 0L));
                tokenUsageStatMapper.insert(stat);
            } else {
                stat.setPromptTokens(stat.getPromptTokens() + (promptTokens != null ? promptTokens : 0L));
                stat.setCompletionTokens(stat.getCompletionTokens() + (completionTokens != null ? completionTokens : 0L));
                stat.setTotalTokens(stat.getTotalTokens() + (promptTokens != null ? promptTokens : 0L) + (completionTokens != null ? completionTokens : 0L));
                tokenUsageStatMapper.updateById(stat);
            }
        } catch (Exception e) {
            log.error("Token用量统计记录失败", e);
        }
    }
}