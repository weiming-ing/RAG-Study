package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDateTime;

@TableName("debug_test_case")
public class DebugTestCase {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;
    private String queryText;
    private Integer topK;
    private Float similarityThreshold;
    private Integer enableHybrid;
    private Float vectorWeight;
    private Float keywordWeight;
    private String kbId;
    private String expectedDocIds;
    private String tags;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getQueryText() { return queryText; }
    public void setQueryText(String queryText) { this.queryText = queryText; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Float getSimilarityThreshold() { return similarityThreshold; }
    public void setSimilarityThreshold(Float similarityThreshold) { this.similarityThreshold = similarityThreshold; }
    public Integer getEnableHybrid() { return enableHybrid; }
    public void setEnableHybrid(Integer enableHybrid) { this.enableHybrid = enableHybrid; }
    public Float getVectorWeight() { return vectorWeight; }
    public void setVectorWeight(Float vectorWeight) { this.vectorWeight = vectorWeight; }
    public Float getKeywordWeight() { return keywordWeight; }
    public void setKeywordWeight(Float keywordWeight) { this.keywordWeight = keywordWeight; }
    public String getKbId() { return kbId; }
    public void setKbId(String kbId) { this.kbId = kbId; }
    public String getExpectedDocIds() { return expectedDocIds; }
    public void setExpectedDocIds(String expectedDocIds) { this.expectedDocIds = expectedDocIds; }
    public String getTags() { return tags; }
    public void setTags(String tags) { this.tags = tags; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}