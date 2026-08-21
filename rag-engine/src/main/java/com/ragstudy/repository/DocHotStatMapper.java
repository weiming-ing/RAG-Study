package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.DocHotStat;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;
import java.util.Map;

@Mapper
public interface DocHotStatMapper extends BaseMapper<DocHotStat> {

    @Select("SELECT document_id, doc_name, SUM(search_count) as searches, SUM(hit_count) as hits, SUM(question_count) as questions FROM doc_hot_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY document_id, doc_name ORDER BY hits DESC LIMIT #{limit}")
    List<Map<String, Object>> topHotDocs(@Param("days") int days, @Param("limit") int limit);

    @Select("SELECT kb_id, SUM(hit_count) as total_hits FROM doc_hot_stat WHERE stat_date >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) GROUP BY kb_id ORDER BY total_hits DESC")
    List<Map<String, Object>> kbHotRank(@Param("days") int days);
}