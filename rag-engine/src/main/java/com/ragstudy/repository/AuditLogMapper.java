package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.AuditLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface AuditLogMapper extends BaseMapper<AuditLog> {

    @Select("SELECT operation, COUNT(*) as cnt FROM audit_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY operation ORDER BY cnt DESC")
    List<Map<String, Object>> countByOperation(@Param("days") int days);

    @Select("SELECT DATE(create_time) as date, COUNT(*) as cnt FROM audit_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY DATE(create_time) ORDER BY date")
    List<Map<String, Object>> countByDay(@Param("days") int days);
}