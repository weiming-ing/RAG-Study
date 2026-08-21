package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@TableName("doc_hot_stat")
public class DocHotStat {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String documentId;
    private String docName;
    private String kbId;
    private Long searchCount;
    private Long hitCount;
    private Long questionCount;
    private Long uniqueVisitors;
    private LocalDate statDate;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getDocName() { return docName; }
    public void setDocName(String docName) { this.docName = docName; }
    public String getKbId() { return kbId; }
    public void setKbId(String kbId) { this.kbId = kbId; }
    public Long getSearchCount() { return searchCount; }
    public void setSearchCount(Long searchCount) { this.searchCount = searchCount; }
    public Long getHitCount() { return hitCount; }
    public void setHitCount(Long hitCount) { this.hitCount = hitCount; }
    public Long getQuestionCount() { return questionCount; }
    public void setQuestionCount(Long questionCount) { this.questionCount = questionCount; }
    public Long getUniqueVisitors() { return uniqueVisitors; }
    public void setUniqueVisitors(Long uniqueVisitors) { this.uniqueVisitors = uniqueVisitors; }
    public LocalDate getStatDate() { return statDate; }
    public void setStatDate(LocalDate statDate) { this.statDate = statDate; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}