package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.TaskMonitor;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;
import java.util.Map;

@Mapper
public interface TaskMonitorMapper extends BaseMapper<TaskMonitor> {

    @Select("SELECT status, COUNT(*) as cnt FROM task_monitor WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY status")
    List<Map<String, Object>> countByStatus(@Param("days") int days);

    @Select("SELECT task_type, COUNT(*) as total, SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) as failed FROM task_monitor WHERE create_time >= DATE_SUB(NOW(), INTERVAL #{days} DAY) GROUP BY task_type")
    List<Map<String, Object>> taskTypeStats(@Param("days") int days);
}