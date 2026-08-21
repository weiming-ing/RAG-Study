package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.SysConfig;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface SysConfigMapper extends BaseMapper<SysConfig> {

    @Select("SELECT * FROM sys_config WHERE config_key = #{key} AND enabled = 1")
    SysConfig findByKey(@Param("key") String key);

    @Select("SELECT * FROM sys_config WHERE config_group = #{group} AND enabled = 1 ORDER BY sort_order")
    List<SysConfig> findByGroup(@Param("group") String group);

    @Select("SELECT config_group, COUNT(*) as count FROM sys_config WHERE enabled = 1 GROUP BY config_group ORDER BY config_group")
    List<java.util.Map<String, Object>> getGroupStats();
}