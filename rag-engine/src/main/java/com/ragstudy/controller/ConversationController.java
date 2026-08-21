package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.ConversationLog;
import com.ragstudy.service.ConversationLogService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/conversations")
public class ConversationController {

    private static final Logger log = LoggerFactory.getLogger(ConversationController.class);

    private final ConversationLogService conversationLogService;

    public ConversationController(ConversationLogService conversationLogService) {
        this.conversationLogService = conversationLogService;
    }

    @GetMapping
    public ApiResponse<IPage<ConversationLog>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String kbId,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer feedback,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate) {
        return ApiResponse.success(conversationLogService.list(
                pageNum, pageSize, kbId, userId, keyword, feedback, startDate, endDate));
    }

    @GetMapping("/grouped")
    public ApiResponse<List<Map<String, Object>>> listGrouped() {
        return ApiResponse.success(conversationLogService.listGroupedByUser());
    }

    @GetMapping("/{id}")
    public ApiResponse<ConversationLog> getById(@PathVariable Long id) {
        ConversationLog log = conversationLogService.getById(id);
        if (log == null) {
            return ApiResponse.error(404, "对话记录不存在");
        }
        return ApiResponse.success(log);
    }

    @PostMapping
    public ApiResponse<ConversationLog> save(@RequestBody ConversationLog log) {
        return ApiResponse.success(conversationLogService.saveLog(log));
    }

    @PostMapping("/save-or-update")
    public ApiResponse<ConversationLog> saveOrUpdate(@RequestBody ConversationLog log) {
        return ApiResponse.success(conversationLogService.saveOrUpdateLog(log));
    }

    @PutMapping("/{id}/feedback")
    public ApiResponse<Void> updateFeedback(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Integer feedback = body.get("feedback") != null ? ((Number) body.get("feedback")).intValue() : 0;
        String reason = (String) body.get("reason");
        String comment = (String) body.get("comment");
        conversationLogService.updateFeedback(id, feedback, reason, comment);
        return ApiResponse.success();
    }

    @GetMapping("/stats/feedback")
    public ApiResponse<?> getFeedbackStats() {
        return ApiResponse.success(conversationLogService.getFeedbackStats());
    }

    @GetMapping("/stats/recent")
    public ApiResponse<Map<String, Object>> getRecentStats(@RequestParam(defaultValue = "7") int days) {
        long count = conversationLogService.getRecentCount(days);
        return ApiResponse.success(Map.of("days", days, "totalConversations", count));
    }

    @GetMapping("/stats/top-kb")
    public ApiResponse<?> getTopKb(@RequestParam(defaultValue = "7") int days, @RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.success(conversationLogService.getTopKb(days, limit));
    }

    @GetMapping("/stats/doc-ref-rank")
    public ApiResponse<?> getDocRefRank(@RequestParam(defaultValue = "7") int days, @RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.success(conversationLogService.getDocRefRank(days, limit));
    }

    @GetMapping("/stats/feedback-distribution")
    public ApiResponse<?> getFeedbackDistribution(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(conversationLogService.getFeedbackDistribution(days));
    }

    @GetMapping("/stats/daily-trend")
    public ApiResponse<?> getDailyTrend(@RequestParam(defaultValue = "7") int days) {
        return ApiResponse.success(Map.of(
            "conversationTrend", conversationLogService.getDailyConversationTrend(days),
            "activeUserTrend", conversationLogService.getDailyActiveUserTrend(days)
        ));
    }

    @GetMapping("/stats/active-user-rank")
    public ApiResponse<?> getActiveUserRank(@RequestParam(defaultValue = "7") int days,
                                            @RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.success(conversationLogService.getActiveUserRank(days, limit));
    }

    @GetMapping("/stats/recent-conversations")
    public ApiResponse<?> getRecentConversations(@RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.success(conversationLogService.getRecentConversations(limit));
    }

    @GetMapping("/stats/today")
    public ApiResponse<?> getTodayStats() {
        return ApiResponse.success(conversationLogService.getTodayStats());
    }
}