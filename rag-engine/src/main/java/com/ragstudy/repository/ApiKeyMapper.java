package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.ApiKey;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ApiKeyMapper extends BaseMapper<ApiKey> {

    @Select("SELECT * FROM api_key WHERE api_key = #{apiKey} AND enabled = 1")
    ApiKey findByApiKey(@Param("apiKey") String apiKey);

    @Update("UPDATE api_key SET total_calls = total_calls + 1, last_used_time = NOW() WHERE api_key = #{apiKey}")
    void incrementCallCount(@Param("apiKey") String apiKey);
}