package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@TableName("chunk_hot_stat")
public class ChunkHotStat {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String chunkId;
    private String documentId;
    private String kbId;
    private Long hitCount;
    private LocalDateTime lastHitTime;
    private LocalDate statDate;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getChunkId() { return chunkId; }
    public void setChunkId(String chunkId) { this.chunkId = chunkId; }
    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getKbId() { return kbId; }
    public void setKbId(String kbId) { this.kbId = kbId; }
    public Long getHitCount() { return hitCount; }
    public void setHitCount(Long hitCount) { this.hitCount = hitCount; }
    public LocalDateTime getLastHitTime() { return lastHitTime; }
    public void setLastHitTime(LocalDateTime lastHitTime) { this.lastHitTime = lastHitTime; }
    public LocalDate getStatDate() { return statDate; }
    public void setStatDate(LocalDate statDate) { this.statDate = statDate; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}