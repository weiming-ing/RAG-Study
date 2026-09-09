package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.ApiCallStat;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;
import java.util.Map;

@Mapper
public interface ApiCallStatMapper extends BaseMapper<ApiCallStat> {

    @Select("SELECT api_path, SUM(call_count) as total_calls, AVG(avg_latency_ms) as avg_latency FROM api_call_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY api_path ORDER BY total_calls DESC")
    List<Map<String, Object>> topApiPaths(@Param("days") int days);

    @Select("SELECT stat_date, SUM(call_count) as total FROM api_call_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY stat_date ORDER BY stat_date")
    List<Map<String, Object>> dailyCallTrend(@Param("days") int days);
}