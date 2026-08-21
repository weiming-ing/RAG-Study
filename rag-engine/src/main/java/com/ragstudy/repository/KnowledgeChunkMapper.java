package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.KnowledgeChunk;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface KnowledgeChunkMapper extends BaseMapper<KnowledgeChunk> {

    @Select("SELECT * FROM knowledge_chunk WHERE document_id = #{documentId} AND deleted = 0 ORDER BY chunk_index")
    List<KnowledgeChunk> selectByDocumentId(@Param("documentId") Long documentId);

    @Select("SELECT * FROM knowledge_chunk WHERE parent_chunk_id = #{parentChunkId} AND deleted = 0")
    List<KnowledgeChunk> selectByParentChunkId(@Param("parentChunkId") String parentChunkId);
}