package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDateTime;

@TableName("knowledge_chunk")
public class KnowledgeChunk {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long documentId;
    private String chunkId;
    private Integer chunkIndex;
    private String content;
    private Integer contentLength;
    private String parentChunkId;
    private Integer parentChunkIndex;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableLogic
    private Integer deleted;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getDocumentId() { return documentId; }
    public void setDocumentId(Long documentId) { this.documentId = documentId; }
    public String getChunkId() { return chunkId; }
    public void setChunkId(String chunkId) { this.chunkId = chunkId; }
    public Integer getChunkIndex() { return chunkIndex; }
    public void setChunkIndex(Integer chunkIndex) { this.chunkIndex = chunkIndex; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public Integer getContentLength() { return contentLength; }
    public void setContentLength(Integer contentLength) { this.contentLength = contentLength; }
    public String getParentChunkId() { return parentChunkId; }
    public void setParentChunkId(String parentChunkId) { this.parentChunkId = parentChunkId; }
    public Integer getParentChunkIndex() { return parentChunkIndex; }
    public void setParentChunkIndex(Integer parentChunkIndex) { this.parentChunkIndex = parentChunkIndex; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public Integer getDeleted() { return deleted; }
    public void setDeleted(Integer deleted) { this.deleted = deleted; }
}