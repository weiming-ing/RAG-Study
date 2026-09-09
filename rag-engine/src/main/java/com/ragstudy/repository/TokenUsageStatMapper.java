package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.TokenUsageStat;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;
import java.util.Map;

@Mapper
public interface TokenUsageStatMapper extends BaseMapper<TokenUsageStat> {

    @Select("SELECT stat_date, SUM(total_tokens) as total FROM token_usage_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY stat_date ORDER BY stat_date")
    List<Map<String, Object>> dailyTokenTrend(@Param("days") int days);

    @Select("SELECT kb_id, SUM(total_tokens) as total FROM token_usage_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY kb_id ORDER BY total DESC LIMIT #{limit}")
    List<Map<String, Object>> topKbByToken(@Param("days") int days, @Param("limit") int limit);
}