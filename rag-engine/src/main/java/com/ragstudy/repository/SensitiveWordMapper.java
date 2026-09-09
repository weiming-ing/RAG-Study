package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.SensitiveWord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;

@Mapper
public interface SensitiveWordMapper extends BaseMapper<SensitiveWord> {

    @Select("SELECT word FROM sensitive_word WHERE enabled=1 AND (kb_id IS NULL OR kb_id=#{kbId})")
    List<String> findActiveWords(@Param("kbId") String kbId);
}