package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ragstudy.model.entity.ConversationLog;
import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.repository.ConversationLogMapper;
import com.ragstudy.repository.KbKnowledgeBaseMapper;
import com.ragstudy.repository.KnowledgeChunkMapper;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import com.ragstudy.repository.SysUserMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 对话日志服务
 *
 * 核心职责：对话记录的存储、查询、统计和反馈管理。
 *
 * 主要功能：
 *   - saveLog / saveOrUpdateLog: 保存对话记录（每次创建新记录，不覆盖历史）
 *   - list: 多条件分页查询（支持 kbId/userId/keyword/feedback/日期范围过滤）
 *   - listGroupedByUser: 按用户分组聚合（管理后台对话列表）
 *   - getTopKb / getDocRefRank: 知识库/文档引用排行榜
 *   - getFeedbackStats / getFeedbackDistribution: 反馈统计分析
 *   - getDailyConversationTrend / getDailyActiveUserTrend: 趋势分析
 *   - updateFeedback: 更新用户反馈（点赞/点踩/原因/评论）
 */
@Service
public class ConversationLogService {

    private static final Logger log = LoggerFactory.getLogger(ConversationLogService.class);

    private final ConversationLogMapper conversationLogMapper;
    private final SysUserMapper sysUserMapper;
    private final KbKnowledgeBaseMapper kbKnowledgeBaseMapper;
    private final KnowledgeDocumentMapper knowledgeDocumentMapper;
    private final KnowledgeChunkMapper knowledgeChunkMapper;

    public ConversationLogService(ConversationLogMapper conversationLogMapper,
                                   SysUserMapper sysUserMapper,
                                   KbKnowledgeBaseMapper kbKnowledgeBaseMapper,
                                   KnowledgeDocumentMapper knowledgeDocumentMapper,
                                   KnowledgeChunkMapper knowledgeChunkMapper) {
        this.conversationLogMapper = conversationLogMapper;
        this.sysUserMapper = sysUserMapper;
        this.kbKnowledgeBaseMapper = kbKnowledgeBaseMapper;
        this.knowledgeDocumentMapper = knowledgeDocumentMapper;
        this.knowledgeChunkMapper = knowledgeChunkMapper;
    }

    /**
     * 保存对话记录（每次创建新记录，不覆盖历史）
     */
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
     * 保存或更新对话记录（按 questionHash 判断是否重复，重复则更新答案）
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

    /**
     * 多条件分页查询对话记录（支持 kbId/userId/keyword/feedback/日期范围过滤）
     */
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

    /**
     * 更新用户反馈（点赞/点踩/原因/评论）
     */
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
        ObjectMapper mapper = new ObjectMapper();

        // 第一遍: 收集所有引用的 (chunkId → docName) 映射，按 documentId 计数
        // 新格式: [{"chunkId": "42_child_15", "docName": "报销管理制度.pdf"}, ...]
        // 旧格式兼容: ["报销管理制度.pdf", ...]
        Map<Long, DocRefCount> docCountMap = new LinkedHashMap<>();

        for (String ref : refs) {
            try {
                // 尝试解析新格式: 数组 of objects
                List<Map<String, Object>> chunkRefs = mapper.readValue(ref, new TypeReference<List<Map<String, Object>>>() {});
                for (Map<String, Object> item : chunkRefs) {
                    String chunkId = (String) item.getOrDefault("chunkId", "");
                    String docName = (String) item.getOrDefault("docName", "");

                    // 从 chunkId 提取 documentId: 格式为 "{documentId}_child_{index}" 或 "{documentId}_parent_{index}"
                    long docId = extractDocIdFromChunkId(chunkId);
                    if (docId > 0) {
                        docCountMap.merge(docId, new DocRefCount(docName, 1), (a, b) -> {
                            a.count += b.count;
                            return a;
                        });
                    } else if (!docName.isEmpty()) {
                        // 没有 chunkId 时，用 docName 作为 key（兼容旧格式）
                        // 使用一个特殊 key 来区分
                        docCountMap.merge(-(long) docName.hashCode(), new DocRefCount(docName, 1), (a, b) -> {
                            a.count += b.count;
                            return a;
                        });
                    }
                }
            } catch (Exception e) {
                // 兼容旧格式: 纯字符串数组 ["doc1.pdf", "doc2.pdf"]
                try {
                    List<String> docNames = mapper.readValue(ref, new TypeReference<List<String>>() {});
                    for (String docName : docNames) {
                        if (docName != null && !docName.isEmpty()) {
                            docCountMap.merge(-(long) docName.hashCode(), new DocRefCount(docName, 1), (a, b) -> {
                                a.count += b.count;
                                return a;
                            });
                        }
                    }
                } catch (Exception ignored) {}
            }
        }

        if (docCountMap.isEmpty()) {
            return new ArrayList<>();
        }

        // 批量查询所有引用的文档
        Set<Long> docIds = docCountMap.keySet().stream()
                .filter(id -> id > 0)
                .collect(Collectors.toSet());
        Map<Long, KnowledgeDocument> docMap = new HashMap<>();
        if (!docIds.isEmpty()) {
            List<KnowledgeDocument> docs = knowledgeDocumentMapper.selectBatchIds(docIds);
            for (KnowledgeDocument doc : docs) {
                if (doc != null) {
                    docMap.put(doc.getId(), doc);
                }
            }
        }

        // 构建结果
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map.Entry<Long, DocRefCount> entry : docCountMap.entrySet()) {
            long docId = entry.getKey();
            int count = entry.getValue().count;
            String docName = entry.getValue().docName;

            Map<String, Object> item = new LinkedHashMap<>();
            item.put("doc_name", docName);
            item.put("cnt", count);

            if (docId > 0) {
                KnowledgeDocument doc = docMap.get(docId);
                if (doc != null) {
                    item.put("doc_id", doc.getId());
                    item.put("kb_id", doc.getKbId());
                } else {
                    item.put("doc_id", docId);
                    item.put("kb_id", null);
                }
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

    /**
     * 从 chunkId 格式 "{documentId}_child_{index}" 或 "{documentId}_parent_{index}" 中提取 documentId
     */
    private long extractDocIdFromChunkId(String chunkId) {
        if (chunkId == null || chunkId.isEmpty()) return -1;
        try {
            // 格式: "42_child_15" 或 "42_parent_3"
            int childIdx = chunkId.indexOf("_child_");
            int parentIdx = chunkId.indexOf("_parent_");
            int splitIdx = childIdx > 0 ? childIdx : (parentIdx > 0 ? parentIdx : -1);
            if (splitIdx > 0) {
                return Long.parseLong(chunkId.substring(0, splitIdx));
            }
        } catch (NumberFormatException ignored) {}
        return -1;
    }

    /** 内部类: 文档引用计数（保留 docName 作为 fallback） */
    private static class DocRefCount {
        String docName;
        int count;
        DocRefCount(String docName, int count) {
            this.docName = docName;
            this.count = count;
        }
    }

    /**
     * 追溯对话记录 → 引用的切片 → 源文档
     *
     * 根据 conversation_log.id 查询 referenced_chunks，
     * 解析 chunk_id 列表，查出每个切片内容及其所属文档信息。
     * 实现完整的 "对话→切片→文档" 追溯链路。
     *
     * @param conversationId conversation_log.id
     * @return 追溯列表，每个元素包含 chunkId, chunkContent, chunkIndex, docId, docName, kbId, kbName
     */
    public List<Map<String, Object>> getConversationChunkTrace(Long conversationId) {
        ConversationLog conversationLog = conversationLogMapper.selectById(conversationId);
        if (conversationLog == null || conversationLog.getReferencedChunks() == null || conversationLog.getReferencedChunks().isEmpty()) {
            return new ArrayList<>();
        }

        ObjectMapper mapper = new ObjectMapper();
        List<Map<String, Object>> result = new ArrayList<>();

        try {
            List<Map<String, Object>> chunkRefs = mapper.readValue(
                    conversationLog.getReferencedChunks(),
                    new TypeReference<List<Map<String, Object>>>() {}
            );

            for (Map<String, Object> ref : chunkRefs) {
                String chunkId = (String) ref.getOrDefault("chunkId", "");
                String docName = (String) ref.getOrDefault("docName", "");

                if (chunkId.isEmpty()) continue;

                // 1. 查切片
                KnowledgeChunk chunk = knowledgeChunkMapper.selectByChunkId(chunkId);
                Map<String, Object> trace = new LinkedHashMap<>();
                trace.put("chunkId", chunkId);
                trace.put("docName", docName);

                if (chunk != null) {
                    trace.put("chunkContent", chunk.getContent() != null
                            ? chunk.getContent().substring(0, Math.min(chunk.getContent().length(), 200))
                            : "");
                    trace.put("chunkIndex", chunk.getChunkIndex());

                    // 2. 查所属文档
                    KnowledgeDocument doc = knowledgeDocumentMapper.selectById(chunk.getDocumentId());
                    if (doc != null) {
                        trace.put("docId", doc.getId());
                        trace.put("docName", doc.getFileName());
                        trace.put("kbId", doc.getKbId());

                        // 3. 查所属知识库
                        if (doc.getKbId() != null) {
                            KbKnowledgeBase kb = kbKnowledgeBaseMapper.selectById(doc.getKbId());
                            trace.put("kbName", kb != null ? kb.getName() : "未知知识库");
                        }
                    } else {
                        trace.put("docId", chunk.getDocumentId());
                        trace.put("kbId", null);
                        trace.put("kbName", "文档已删除");
                    }
                } else {
                    trace.put("chunkContent", "");
                    trace.put("chunkIndex", null);
                    trace.put("docId", extractDocIdFromChunkId(chunkId));
                    trace.put("kbId", null);
                    trace.put("kbName", "切片已删除");
                }
                result.add(trace);
            }
        } catch (Exception e) {
            log.warn("解析 referenced_chunks 失败: conversationId={}, error={}", conversationId, e.getMessage());
        }

        return result;
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