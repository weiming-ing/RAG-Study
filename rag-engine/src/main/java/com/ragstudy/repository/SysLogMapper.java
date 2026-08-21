package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.SysLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface SysLogMapper extends BaseMapper<SysLog> {

    @Select("SELECT log_level, COUNT(*) as count FROM sys_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY log_level")
    List<Map<String, Object>> countByLevel(@Param("days") int days);

    @Select("SELECT log_module, COUNT(*) as count FROM sys_log WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY log_module ORDER BY count DESC LIMIT 10")
    List<Map<String, Object>> countByModule(@Param("days") int days);

    @org.apache.ibatis.annotations.Delete("DELETE FROM sys_log WHERE create_time < DATE_SUB(NOW(), INTERVAL #{days} DAY)")
    int cleanExpired(@Param("days") int days);
}