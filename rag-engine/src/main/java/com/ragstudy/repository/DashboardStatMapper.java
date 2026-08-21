package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.DashboardStat;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DashboardStatMapper extends BaseMapper<DashboardStat> {
}