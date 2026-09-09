package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@TableName("api_call_stat")
public class ApiCallStat {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String kbId;
    private String apiPath;
    private Long callCount;
    private Long successCount;
    private Long failCount;
    private Double avgLatencyMs;
    private LocalDate statDate;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getKbId() { return kbId; }
    public void setKbId(String kbId) { this.kbId = kbId; }
    public String getApiPath() { return apiPath; }
    public void setApiPath(String apiPath) { this.apiPath = apiPath; }
    public Long getCallCount() { return callCount; }
    public void setCallCount(Long callCount) { this.callCount = callCount; }
    public Long getSuccessCount() { return successCount; }
    public void setSuccessCount(Long successCount) { this.successCount = successCount; }
    public Long getFailCount() { return failCount; }
    public void setFailCount(Long failCount) { this.failCount = failCount; }
    public Double getAvgLatencyMs() { return avgLatencyMs; }
    public void setAvgLatencyMs(Double avgLatencyMs) { this.avgLatencyMs = avgLatencyMs; }
    public LocalDate getStatDate() { return statDate; }
    public void setStatDate(LocalDate statDate) { this.statDate = statDate; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}