package com.ragstudy.model.vo;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;

public class DocumentVO {

    private Long id;

    @JsonProperty("name")
    private String fileName;

    private String fileType;
    private Long fileSize;
    private String department;
    private String category;

    @JsonProperty("chunkCount")
    private Integer totalChunks;

    private Integer totalParentChunks;
    private String status;
    private String summary;
    private LocalDateTime createTime;

    @JsonProperty("kbId")
    private Long knowledgeBaseId;

    @JsonProperty("kbName")
    private String knowledgeBaseName;

    public DocumentVO() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
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
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }

    public Long getKnowledgeBaseId() { return knowledgeBaseId; }
    public void setKnowledgeBaseId(Long knowledgeBaseId) { this.knowledgeBaseId = knowledgeBaseId; }
    public String getKnowledgeBaseName() { return knowledgeBaseName; }
    public void setKnowledgeBaseName(String knowledgeBaseName) { this.knowledgeBaseName = knowledgeBaseName; }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private Long id;
        private String fileName;
        private String fileType;
        private Long fileSize;
        private String department;
        private String category;
        private Integer totalChunks;
        private Integer totalParentChunks;
        private String status;
        private String summary;
        private LocalDateTime createTime;
        private Long knowledgeBaseId;
        private String knowledgeBaseName;

        public Builder id(Long id) { this.id = id; return this; }
        public Builder fileName(String fileName) { this.fileName = fileName; return this; }
        public Builder fileType(String fileType) { this.fileType = fileType; return this; }
        public Builder fileSize(Long fileSize) { this.fileSize = fileSize; return this; }
        public Builder department(String department) { this.department = department; return this; }
        public Builder category(String category) { this.category = category; return this; }
        public Builder totalChunks(Integer totalChunks) { this.totalChunks = totalChunks; return this; }
        public Builder totalParentChunks(Integer totalParentChunks) { this.totalParentChunks = totalParentChunks; return this; }
        public Builder status(String status) { this.status = status; return this; }
        public Builder summary(String summary) { this.summary = summary; return this; }
        public Builder createTime(LocalDateTime createTime) { this.createTime = createTime; return this; }
        public Builder knowledgeBaseId(Long knowledgeBaseId) { this.knowledgeBaseId = knowledgeBaseId; return this; }
        public Builder knowledgeBaseName(String knowledgeBaseName) { this.knowledgeBaseName = knowledgeBaseName; return this; }

        public DocumentVO build() {
            DocumentVO vo = new DocumentVO();
            vo.id = this.id;
            vo.fileName = this.fileName;
            vo.fileType = this.fileType;
            vo.fileSize = this.fileSize;
            vo.department = this.department;
            vo.category = this.category;
            vo.totalChunks = this.totalChunks;
            vo.totalParentChunks = this.totalParentChunks;
            vo.status = this.status;
            vo.summary = this.summary;
            vo.createTime = this.createTime;
            vo.knowledgeBaseId = this.knowledgeBaseId;
            vo.knowledgeBaseName = this.knowledgeBaseName;
            return vo;
        }
    }
}