package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.ConversationLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface ConversationLogMapper extends BaseMapper<ConversationLog> {

    @Select("SELECT feedback_reason, COUNT(*) as cnt FROM conversation_log WHERE feedback = -1 AND feedback_reason IS NOT NULL GROUP BY feedback_reason ORDER BY cnt DESC")
    List<Map<String, Object>> countByFeedbackReason();

    @Select("SELECT COUNT(*) FROM conversation_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    long countRecent(@Param("days") int days);

    @Select("SELECT kb_id, COUNT(*) as cnt FROM conversation_log WHERE kb_id IS NOT NULL AND create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY kb_id ORDER BY cnt DESC LIMIT #{limit}")
    List<Map<String, Object>> topKbByConversations(@Param("days") int days, @Param("limit") int limit);

    @Select("SELECT user_id, MAX(id) as latest_id, COUNT(*) as total_count, MAX(create_time) as latest_time " +
            "FROM conversation_log WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY latest_time DESC")
    List<Map<String, Object>> groupByUser();

    @Select("SELECT * FROM conversation_log WHERE user_id = #{userId} ORDER BY create_time DESC LIMIT 1")
    ConversationLog selectLatestByUserId(@Param("userId") Long userId);

    @Select("SELECT " +
            "SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive_count, " +
            "SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as negative_count, " +
            "SUM(CASE WHEN feedback = 0 OR feedback IS NULL THEN 1 ELSE 0 END) as neutral_count " +
            "FROM conversation_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    Map<String, Object> feedbackDistribution(@Param("days") int days);

    @Select("SELECT DATE(create_time) as stat_date, COUNT(*) as total FROM conversation_log " +
            "WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "GROUP BY DATE(create_time) ORDER BY stat_date")
    List<Map<String, Object>> dailyConversationTrend(@Param("days") int days);

    @Select("SELECT DATE(create_time) as stat_date, COUNT(DISTINCT user_id) as total FROM conversation_log " +
            "WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) AND user_id IS NOT NULL " +
            "GROUP BY DATE(create_time) ORDER BY stat_date")
    List<Map<String, Object>> dailyActiveUserTrend(@Param("days") int days);

    @Select("SELECT user_id, COUNT(*) as cnt, MAX(create_time) as last_time " +
            "FROM conversation_log " +
            "WHERE user_id IS NOT NULL AND create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) " +
            "GROUP BY user_id ORDER BY cnt DESC LIMIT #{limit}")
    List<Map<String, Object>> activeUserRank(@Param("days") int days, @Param("limit") int limit);

    @Select("SELECT id, user_id, question, kb_id, create_time, feedback " +
            "FROM conversation_log " +
            "ORDER BY create_time DESC LIMIT #{limit}")
    List<Map<String, Object>> recentConversations(@Param("limit") int limit);

    @Select("SELECT COUNT(*) as cnt FROM conversation_log WHERE DATE(create_time) = CURDATE()")
    long countToday();

    @Select("SELECT COUNT(*) as cnt FROM conversation_log WHERE YEARWEEK(create_time, 1) = YEARWEEK(CURDATE(), 1)")
    long countThisWeek();

    @Select("SELECT COUNT(*) as cnt FROM conversation_log WHERE DATE_FORMAT(create_time, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')")
    long countThisMonth();

    @Select("SELECT referenced_chunks FROM conversation_log WHERE referenced_chunks IS NOT NULL AND referenced_chunks != '' AND referenced_chunks != '[]' AND create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    List<String> getReferencedChunks(@Param("days") int days);
}