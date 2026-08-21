package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.AccessControl;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AccessControlMapper extends BaseMapper<AccessControl> {
}