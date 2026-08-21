package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@TableName("dashboard_stat")
public class DashboardStat {

    @TableId(type = IdType.AUTO)
    private Long id;
    private LocalDate statDate;
    private Integer totalKbCount;
    private Integer totalDocCount;
    private Integer totalChunkCount;
    private Integer totalQuestionCount;
    private Integer totalApiCalls;
    private Long totalTokenUsage;
    private Integer activeUserCount;
    private Integer newUserCount;
    private Double avgLatencyMs;
    private Double successRate;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public LocalDate getStatDate() { return statDate; }
    public void setStatDate(LocalDate statDate) { this.statDate = statDate; }
    public Integer getTotalKbCount() { return totalKbCount; }
    public void setTotalKbCount(Integer totalKbCount) { this.totalKbCount = totalKbCount; }
    public Integer getTotalDocCount() { return totalDocCount; }
    public void setTotalDocCount(Integer totalDocCount) { this.totalDocCount = totalDocCount; }
    public Integer getTotalChunkCount() { return totalChunkCount; }
    public void setTotalChunkCount(Integer totalChunkCount) { this.totalChunkCount = totalChunkCount; }
    public Integer getTotalQuestionCount() { return totalQuestionCount; }
    public void setTotalQuestionCount(Integer totalQuestionCount) { this.totalQuestionCount = totalQuestionCount; }
    public Integer getTotalApiCalls() { return totalApiCalls; }
    public void setTotalApiCalls(Integer totalApiCalls) { this.totalApiCalls = totalApiCalls; }
    public Long getTotalTokenUsage() { return totalTokenUsage; }
    public void setTotalTokenUsage(Long totalTokenUsage) { this.totalTokenUsage = totalTokenUsage; }
    public Integer getActiveUserCount() { return activeUserCount; }
    public void setActiveUserCount(Integer activeUserCount) { this.activeUserCount = activeUserCount; }
    public Integer getNewUserCount() { return newUserCount; }
    public void setNewUserCount(Integer newUserCount) { this.newUserCount = newUserCount; }
    public Double getAvgLatencyMs() { return avgLatencyMs; }
    public void setAvgLatencyMs(Double avgLatencyMs) { this.avgLatencyMs = avgLatencyMs; }
    public Double getSuccessRate() { return successRate; }
    public void setSuccessRate(Double successRate) { this.successRate = successRate; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}