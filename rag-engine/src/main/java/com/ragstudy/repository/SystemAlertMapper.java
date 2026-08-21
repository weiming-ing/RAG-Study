package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.SystemAlert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;
import java.util.Map;

@Mapper
public interface SystemAlertMapper extends BaseMapper<SystemAlert> {

    @Select("SELECT alert_level, COUNT(*) as cnt FROM system_alert WHERE status='ACTIVE' GROUP BY alert_level")
    List<Map<String, Object>> countActiveByLevel();

    @Select("SELECT COUNT(*) FROM system_alert WHERE status='ACTIVE' AND create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    long countActiveRecent(@Param("days") int days);
}