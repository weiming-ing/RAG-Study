package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ragstudy.model.entity.ConversationLog;
import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.repository.ConversationLogMapper;
import com.ragstudy.repository.KbKnowledgeBaseMapper;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import com.ragstudy.repository.SysUserMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class ConversationLogService {

    private final ConversationLogMapper conversationLogMapper;
    private final SysUserMapper sysUserMapper;
    private final KbKnowledgeBaseMapper kbKnowledgeBaseMapper;
    private final KnowledgeDocumentMapper knowledgeDocumentMapper;

    public ConversationLogService(ConversationLogMapper conversationLogMapper,
                                   SysUserMapper sysUserMapper,
                                   KbKnowledgeBaseMapper kbKnowledgeBaseMapper,
                                   KnowledgeDocumentMapper knowledgeDocumentMapper) {
        this.conversationLogMapper = conversationLogMapper;
        this.sysUserMapper = sysUserMapper;
        this.kbKnowledgeBaseMapper = kbKnowledgeBaseMapper;
        this.knowledgeDocumentMapper = knowledgeDocumentMapper;
    }

    public ConversationLog saveLog(ConversationLog log) {
        log.setCreateTime(LocalDateTime.now());
        if (log.getTotalCount() == null) {
            log.setTotalCount(1);
        }
        // 构建对话记录数据
        String conversationData = buildConversationData(log.getQuestion(), log.getAnswer());
        log.setConversationData(conversationData);
        conversationLogMapper.insert(log);
        return log;
    }

    /**
     * 保存对话记录（每次对话创建一条新记录，不覆盖旧记录）
     * 管理平台通过 GROUP BY user_id 聚合展示，详情页可查看所有历史记录
     */
    public ConversationLog saveOrUpdateLog(ConversationLog log) {
        // 每次对话都创建新记录，确保每条历史记录独立可查
        return saveLog(log);
    }

    private String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }

    private String buildConversationData(String question, String answer) {
        return "{\"q\":\"" + escapeJson(question) + "\",\"a\":\"" + escapeJson(answer) + "\",\"t\":\"" + LocalDateTime.now() + "\"}";
    }

    public IPage<ConversationLog> list(int pageNum, int pageSize, String kbId, Long userId,
                                        String keyword, Integer feedback, String startDate, String endDate) {
        Page<ConversationLog> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<ConversationLog> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(kbId)) {
            wrapper.eq(ConversationLog::getKbId, kbId);
        }
        if (userId != null) {
            wrapper.eq(ConversationLog::getUserId, userId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(ConversationLog::getQuestion, keyword)
                    .or().like(ConversationLog::getAnswer, keyword));
        }
        if (feedback != null) {
            wrapper.eq(ConversationLog::getFeedback, feedback);
        }
        if (StringUtils.hasText(startDate)) {
            wrapper.ge(ConversationLog::getCreateTime, startDate + " 00:00:00");
        }
        if (StringUtils.hasText(endDate)) {
            wrapper.le(ConversationLog::getCreateTime, endDate + " 23:59:59");
        }
        wrapper.orderByDesc(ConversationLog::getCreateTime);

        IPage<ConversationLog> result = conversationLogMapper.selectPage(page, wrapper);

        List<ConversationLog> records = result.getRecords();
        if (!records.isEmpty()) {
            Set<Long> userIds = records.stream()
                    .map(ConversationLog::getUserId)
                    .filter(Objects::nonNull)
                    .collect(Collectors.toSet());
            Set<String> kbIds = records.stream()
                    .map(ConversationLog::getKbId)
                    .filter(StringUtils::hasText)
                    .collect(Collectors.toSet());

            Map<Long, String> userMap = new HashMap<>();
            if (!userIds.isEmpty()) {
                List<SysUser> users = sysUserMapper.selectBatchIds(userIds);
                for (SysUser user : users) {
                    userMap.put(user.getId(), user.getUsername());
                }
            }

            Map<String, String> kbMap = new HashMap<>();
            if (!kbIds.isEmpty()) {
                // kbId 是 String 类型，KbKnowledgeBase 主键是 Long，需要转换
                Set<Long> kbLongIds = kbIds.stream()
                        .map(id -> {
                            try { return Long.parseLong(id); }
                            catch (NumberFormatException e) { return null; }
                        })
                        .filter(Objects::nonNull)
                        .collect(Collectors.toSet());
                if (!kbLongIds.isEmpty()) {
                    List<KbKnowledgeBase> kbs = kbKnowledgeBaseMapper.selectBatchIds(kbLongIds);
                    for (KbKnowledgeBase kb : kbs) {
                        kbMap.put(String.valueOf(kb.getId()), kb.getName());
                    }
                }
            }

            for (ConversationLog record : records) {
                if (record.getUserId() != null) {
                    record.setUsername(userMap.getOrDefault(record.getUserId(), ""));
                }
                if (StringUtils.hasText(record.getKbId())) {
                    record.setKbName(kbMap.getOrDefault(record.getKbId(), ""));
                }
            }
        }

        return result;
    }

    /**
     * 按用户分组获取对话记录（每个用户一条，含最新问答和总轮次）
     */
    public List<Map<String, Object>> listGroupedByUser() {
        List<Map<String, Object>> groups = conversationLogMapper.groupByUser();
        if (groups.isEmpty()) return groups;

        // 获取用户信息
        Set<Long> userIds = groups.stream()
                .map(g -> ((Number) g.get("user_id")).longValue())
                .collect(Collectors.toSet());
        Map<Long, String> userMap = new HashMap<>();
        if (!userIds.isEmpty()) {
            List<SysUser> users = sysUserMapper.selectBatchIds(userIds);
            for (SysUser user : users) {
                userMap.put(user.getId(), user.getUsername());
            }
        }

        // 为每个分组补充用户信息和最新记录详情
        for (Map<String, Object> group : groups) {
            Long userId = ((Number) group.get("user_id")).longValue();
            group.put("username", userMap.getOrDefault(userId, ""));
            group.put("displayName", "");

            // 获取最新一条记录补充详情
            ConversationLog latest = conversationLogMapper.selectLatestByUserId(userId);
            if (latest != null) {
                group.put("latestQuestion", latest.getQuestion());
                group.put("latestAnswer", latest.getAnswer());
                group.put("kbId", latest.getKbId());
                group.put("latestId", latest.getId());
                // total_count 来自 GROUP BY COUNT(*)，是真实记录数，不需要覆盖
            }
        }

        return groups;
    }

    public ConversationLog getById(Long id) {
        return conversationLogMapper.selectById(id);
    }

    public void updateFeedback(Long id, Integer feedback, String reason, String comment) {
        ConversationLog log = conversationLogMapper.selectById(id);
        if (log == null) {
            return;
        }
        log.setFeedback(feedback);
        log.setFeedbackReason(reason);
        log.setFeedbackComment(comment);
        conversationLogMapper.updateById(log);
    }

    public List<Map<String, Object>> getFeedbackStats() {
        return conversationLogMapper.countByFeedbackReason();
    }

    public long getRecentCount(int days) {
        return conversationLogMapper.countRecent(days);
    }

    public List<Map<String, Object>> getTopKb(int days, int limit) {
        List<Map<String, Object>> raw = conversationLogMapper.topKbByConversations(days, limit);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : raw) {
            Map<String, Object> enriched = new LinkedHashMap<>(row);
            Object kbIdObj = row.get("kb_id");
            if (kbIdObj != null) {
                try {
                    Long kbId = Long.valueOf(kbIdObj.toString());
                    KbKnowledgeBase kb = kbKnowledgeBaseMapper.selectById(kbId);
                    enriched.put("kb_name", kb != null ? kb.getName() : "未知知识库");
                } catch (Exception ignored) {
                    enriched.put("kb_name", "未知知识库");
                }
            } else {
                enriched.put("kb_name", "未知知识库");
            }
            result.add(enriched);
        }
        return result;
    }

    public long count() {
        return conversationLogMapper.selectCount(null);
    }

    public Map<String, Object> getFeedbackDistribution(int days) {
        return conversationLogMapper.feedbackDistribution(days);
    }

    public List<Map<String, Object>> getDailyConversationTrend(int days) {
        return conversationLogMapper.dailyConversationTrend(days);
    }

    public List<Map<String, Object>> getDailyActiveUserTrend(int days) {
        return conversationLogMapper.dailyActiveUserTrend(days);
    }

    public List<Map<String, Object>> getActiveUserRank(int days, int limit) {
        List<Map<String, Object>> raw = conversationLogMapper.activeUserRank(days, limit);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : raw) {
            Map<String, Object> enriched = new LinkedHashMap<>(row);
            Object userIdObj = row.get("user_id");
            String username = null;
            if (userIdObj != null) {
                try {
                    Long userId = Long.valueOf(userIdObj.toString());
                    SysUser user = sysUserMapper.selectById(userId);
                    if (user != null) {
                        username = user.getUsername();
                    }
                } catch (Exception ignored) {}
            }
            enriched.put("username", username != null ? username : "未知用户");
            result.add(enriched);
        }
        return result;
    }

    public List<Map<String, Object>> getRecentConversations(int limit) {
        List<Map<String, Object>> raw = conversationLogMapper.recentConversations(limit);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> row : raw) {
            Map<String, Object> enriched = new LinkedHashMap<>(row);
            Object userIdObj = row.get("user_id");
            if (userIdObj != null) {
                try {
                    Long userId = Long.valueOf(userIdObj.toString());
                    SysUser user = sysUserMapper.selectById(userId);
                    enriched.put("username", user != null ? user.getUsername() : "未知用户");
                } catch (Exception ignored) {
                    enriched.put("username", "未知用户");
                }
            } else {
                enriched.put("username", "未知用户");
            }

            Object kbIdObj = row.get("kb_id");
            if (kbIdObj != null) {
                try {
                    Long kbId = Long.valueOf(kbIdObj.toString());
                    KbKnowledgeBase kb = kbKnowledgeBaseMapper.selectById(kbId);
                    enriched.put("kb_name", kb != null ? kb.getName() : "未知知识库");
                } catch (Exception ignored) {
                    enriched.put("kb_name", "未知知识库");
                }
            } else {
                enriched.put("kb_name", "未知知识库");
            }
            result.add(enriched);
        }
        return result;
    }

    public List<Map<String, Object>> getDocRefRank(int days, int limit) {
        List<String> refs = conversationLogMapper.getReferencedChunks(days);
        Map<String, Integer> countMap = new LinkedHashMap<>();
        ObjectMapper mapper = new ObjectMapper();
        for (String ref : refs) {
            try {
                List<String> docNames = mapper.readValue(ref, new TypeReference<List<String>>() {});
                for (String docName : docNames) {
                    if (docName != null && !docName.isEmpty()) {
                        countMap.merge(docName, 1, Integer::sum);
                    }
                }
            } catch (Exception ignored) {}
        }

        if (countMap.isEmpty()) {
            return new ArrayList<>();
        }

        Map<String, KnowledgeDocument> docMap = new LinkedHashMap<>();
        List<KnowledgeDocument> allDocs = knowledgeDocumentMapper.selectList(null);
        if (allDocs != null) {
            for (KnowledgeDocument doc : allDocs) {
                if (doc.getFileName() != null && !doc.getFileName().isEmpty()) {
                    docMap.put(doc.getFileName(), doc);
                }
            }
        }

        List<Map<String, Object>> result = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : countMap.entrySet()) {
            String docName = entry.getKey();
            Integer count = entry.getValue();
            KnowledgeDocument doc = docMap.get(docName);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("doc_name", docName);
            item.put("cnt", count);
            if (doc != null) {
                item.put("doc_id", doc.getId());
                item.put("kb_id", doc.getKbId());
            } else {
                item.put("doc_id", null);
                item.put("kb_id", null);
            }
            result.add(item);
        }

        return result.stream()
            .sorted((a, b) -> ((Integer) b.get("cnt")).compareTo((Integer) a.get("cnt")))
            .limit(limit)
            .collect(Collectors.toList());
    }

    public Map<String, Object> getTodayStats() {
        long today = conversationLogMapper.countToday();
        long thisWeek = conversationLogMapper.countThisWeek();
        long thisMonth = conversationLogMapper.countThisMonth();
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("today", today);
        stats.put("thisWeek", thisWeek);
        stats.put("thisMonth", thisMonth);
        return stats;
    }
}