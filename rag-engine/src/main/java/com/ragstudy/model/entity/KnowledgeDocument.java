package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDateTime;

@TableName("knowledge_document")
public class KnowledgeDocument {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String fileName;
    private String fileType;
    private Long fileSize;
    private Long kbId;
    private String department;
    private String category;
    private Integer totalChunks;
    private Integer totalParentChunks;
    private String status;
    private String summary;
    private String content;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
    public Long getKbId() { return kbId; }
    public void setKbId(Long kbId) { this.kbId = kbId; }
    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }
    public Integer getTotalChunks() { return totalChunks; }
    public void setTotalChunks(Integer totalChunks) { this.totalChunks = totalChunks; }
    public Integer getTotalParentChunks() { return totalParentChunks; }
    public void setTotalParentChunks(Integer totalParentChunks) { this.totalParentChunks = totalParentChunks; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
    public Integer getDeleted() { return deleted; }
    public void setDeleted(Integer deleted) { this.deleted = deleted; }
}