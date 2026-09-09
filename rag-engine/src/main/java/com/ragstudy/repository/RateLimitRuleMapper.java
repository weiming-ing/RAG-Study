package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.RateLimitRule;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface RateLimitRuleMapper extends BaseMapper<RateLimitRule> {
}