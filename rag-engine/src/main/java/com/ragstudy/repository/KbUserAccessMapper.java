package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.KbUserAccess;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface KbUserAccessMapper extends BaseMapper<KbUserAccess> {

    @Select("SELECT user_id FROM kb_user_access WHERE kb_id = #{kbId}")
    List<Long> selectUserIdsByKbId(@Param("kbId") Long kbId);

    @Select("SELECT access_level FROM kb_user_access WHERE kb_id = #{kbId} AND user_id = #{userId}")
    String selectAccessLevel(@Param("kbId") Long kbId, @Param("userId") Long userId);
}