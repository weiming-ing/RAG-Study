package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.ParseTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ParseTaskMapper extends BaseMapper<ParseTask> {

    @Select("SELECT * FROM parse_task WHERE document_id = #{documentId} ORDER BY create_time DESC")
    List<ParseTask> selectByDocumentId(@Param("documentId") String documentId);

    @Select("SELECT * FROM parse_task WHERE status = 'PENDING' ORDER BY create_time ASC LIMIT #{limit}")
    List<ParseTask> selectPendingTasks(@Param("limit") int limit);
}