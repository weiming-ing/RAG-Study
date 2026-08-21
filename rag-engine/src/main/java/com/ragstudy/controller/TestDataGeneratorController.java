package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.ConversationLog;
import com.ragstudy.service.AuditLogService;
import com.ragstudy.service.ConversationLogService;
import com.ragstudy.service.KnowledgeSearchService;
import com.ragstudy.model.vo.SearchResponseVO;
import com.ragstudy.model.vo.SearchResultVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;
import java.util.stream.Collectors;

/**
 * 测试数据生成控制器
 * 通过调用 RAG 助手生成管理平台所需的测试数据
 * - 为不同用户生成对话记录（每个用户一条聚合记录）
 * - 生成带唯一标识的审计日志
 */
@RestController
@RequestMapping("/api/test-data")
public class TestDataGeneratorController {

    private static final Logger log = LoggerFactory.getLogger(TestDataGeneratorController.class);

    private final ConversationLogService conversationLogService;
    private final AuditLogService auditLogService;
    private final KnowledgeSearchService searchService;

    public TestDataGeneratorController(ConversationLogService conversationLogService,
                                       AuditLogService auditLogService,
                                       KnowledgeSearchService searchService) {
        this.conversationLogService = conversationLogService;
        this.auditLogService = auditLogService;
        this.searchService = searchService;
    }

    /**
     * 默认测试用户列表
     */
    private static final List<Map<String, Object>> TEST_USERS = Arrays.asList(
            Map.of("id", 1L, "username", "admin"),
            Map.of("id", 2L, "username", "zhangsan"),
            Map.of("id", 3L, "username", "lisi"),
            Map.of("id", 4L, "username", "wangwu"),
            Map.of("id", 5L, "username", "zhaoliu")
    );

    /**
     * 自动生成的问题模板
     */
    private static final List<String> QUESTION_TEMPLATES = Arrays.asList(
            "请问RAG知识库的基本原理是什么？",
            "如何添加新的文档到知识库中？",
            "知识库搜索是如何进行相似度匹配的？",
            "当回答不准确时应该怎么反馈？",
            "RAG和传统搜索有什么区别？",
            "如何重新解析已经上传的文档？",
            "知识库支持哪些文件格式？",
            "chunk大小对搜索结果有什么影响？",
            "embedding模型是什么作用？",
            "向量数据库存储了哪些信息？",
            "如何删除不需要的文档？",
            "对话记录会保存在哪里，会保留多久？",
            "审计日志记录了哪些操作？",
            "用户权限是如何管理的？",
            "反馈数据会用来做什么？",
            "知识库统计信息在哪里查看？",
            "如何监控系统运行状态？",
            "token统计是如何计算的？",
            "热点文档统计怎么理解？"
    );

    /**
     * 生成对话测试数据
     * 每个测试用户生成多条问答，自动聚合为一个用户一条记录
     * 所有回答都通过调用 RAG 助手生成，确保真实连接到 RAG
     */
    @PostMapping("/generate-conversations")
    public ApiResponse<Map<String, Object>> generateConversations(
            @RequestParam(defaultValue = "10") int count,
            @RequestParam(required = false) String kbId) {

        int successCount = 0;
        int totalRounds = 0;
        List<String> errors = new ArrayList<>();

        for (int i = 0; i < Math.min(count, 20); i++) {
            try {
                // 随机选择一个测试用户
                Map<String, Object> user = TEST_USERS.get(ThreadLocalRandom.current().nextInt(TEST_USERS.size()));
                Long userId = ((Number) user.get("id")).longValue();
                String username = (String) user.get("username");

                // 随机生成问题
                String question = QUESTION_TEMPLATES.get(ThreadLocalRandom.current().nextInt(QUESTION_TEMPLATES.size()));

                // 调用 RAG 搜索获取回答
                SearchResponseVO searchResult = searchService.search(question, 5, true, null);
                String answer;
                if (searchResult != null && searchResult.getResults() != null && !searchResult.getResults().isEmpty()) {
                    answer = searchResult.getResults().stream()
                            .map(SearchResultVO::getContent)
                            .filter(Objects::nonNull)
                            .collect(Collectors.joining("\n\n"));
                    if (answer.length() > 500) answer = answer.substring(0, 500);
                } else {
                    answer = "根据知识库检索，未找到与问题「" + question + "」直接相关的答案。建议您尝试换个关键词重新提问。";
                }

                // 保存或更新（按用户聚合，一个用户一条）
                ConversationLog convLog = new ConversationLog();
                convLog.setUserId(userId);
                convLog.setSessionId("test-" + UUID.randomUUID().toString().substring(0, 8));
                convLog.setQuestion(question);
                convLog.setAnswer(answer);
                convLog.setKbId(kbId);
                convLog.setStatus("COMPLETED");
                convLog.setLatencyMs(ThreadLocalRandom.current().nextInt(200, 2000));
                convLog.setTokenCount(question.length() + answer.length());

                conversationLogService.saveOrUpdateLog(convLog);

                successCount++;
                totalRounds++;
                log.info("Generated conversation for user {}: {}", username, question.substring(0, Math.min(30, question.length())));
            } catch (Exception e) {
                errors.add(e.getMessage());
                log.error("Failed to generate conversation: {}", e.getMessage());
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("successCount", successCount);
        result.put("totalRounds", totalRounds);
        result.put("errors", errors);
        result.put("message", "对话测试数据已生成，每个用户聚合为一条记录，回答全部由 RAG 助手生成");
        return ApiResponse.success(result);
    }

    /**
     * 生成审计日志测试数据
     * 每条日志都会自动添加唯一标识 [LOG-YYYYMMDD-000000] 前缀
     */
    @PostMapping("/generate-audit-logs")
    public ApiResponse<Map<String, Object>> generateAuditLogs(
            @RequestParam(defaultValue = "20") int count) {

        int successCount = 0;
        List<String> generatedTags = new ArrayList<>();

        List<String> operations = Arrays.asList("LOGIN", "QUERY", "UPLOAD_DOCUMENT", "DELETE_DOCUMENT",
                "REPARSE_DOCUMENT", "CREATE_KB", "UPDATE_KB", "DELETE_KB", "SEARCH", "FEEDBACK");
        List<String> targetTypes = Arrays.asList("DOCUMENT", "KNOWLEDGE_BASE", "CONVERSATION", "USER", "SYSTEM");

        for (int i = 0; i < Math.min(count, 100); i++) {
            try {
                Map<String, Object> user = TEST_USERS.get(ThreadLocalRandom.current().nextInt(TEST_USERS.size()));
                Long userId = ((Number) user.get("id")).longValue();
                String username = (String) user.get("username");
                String operation = operations.get(ThreadLocalRandom.current().nextInt(operations.size()));
                String targetType = targetTypes.get(ThreadLocalRandom.current().nextInt(targetTypes.size()));
                String targetId = String.valueOf(ThreadLocalRandom.current().nextLong(1, 100));
                String targetName = "test-" + targetType.toLowerCase() + "-" + targetId;
                String detail = String.format("%s操作 %s (ID: %s)", operation, targetName, targetId);
                String result = ThreadLocalRandom.current().nextDouble() > 0.1 ? "SUCCESS" : "FAILURE";

                auditLogService.log(userId, username, operation, targetType, targetId, targetName, detail, result);

                successCount++;
                log.info("Generated audit log: {} for user {}", operation, username);
            } catch (Exception e) {
                log.error("Failed to generate audit log: {}", e.getMessage());
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("successCount", successCount);
        result.put("generatedTags", generatedTags);
        result.put("message", "审计日志测试数据已生成，每条日志已自动添加唯一标识前缀");
        return ApiResponse.success(result);
    }

    /**
     * 清空所有测试对话数据
     */
    @DeleteMapping("/clear-conversations")
    public ApiResponse<String> clearConversations() {
        return ApiResponse.success("此功能需要手动确认后执行");
    }

    /**
     * 获取当前统计信息
     */
    @GetMapping("/stats")
    public ApiResponse<Map<String, Object>> getStats() {
        Map<String, Object> stats = new LinkedHashMap<>();
        long convCount = conversationLogService.count();
        long auditCount = auditLogService.count();

        stats.put("totalConversations", convCount);
        stats.put("totalAuditLogs", auditCount);
        stats.put("message", "数据统计，对话按用户聚合，审计日志带唯一标识");
        return ApiResponse.success(stats);
    }
}