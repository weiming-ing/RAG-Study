package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDateTime;

@TableName("rate_limit_rule")
public class RateLimitRule {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String ruleName;
    private String targetType;
    private String targetValue;
    private String limitType;
    private Integer limitCount;
    private Integer windowSeconds;
    private Integer enabled;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getRuleName() { return ruleName; }
    public void setRuleName(String ruleName) { this.ruleName = ruleName; }
    public String getTargetType() { return targetType; }
    public void setTargetType(String targetType) { this.targetType = targetType; }
    public String getTargetValue() { return targetValue; }
    public void setTargetValue(String targetValue) { this.targetValue = targetValue; }
    public String getLimitType() { return limitType; }
    public void setLimitType(String limitType) { this.limitType = limitType; }
    public Integer getLimitCount() { return limitCount; }
    public void setLimitCount(Integer limitCount) { this.limitCount = limitCount; }
    public Integer getWindowSeconds() { return windowSeconds; }
    public void setWindowSeconds(Integer windowSeconds) { this.windowSeconds = windowSeconds; }
    public Integer getEnabled() { return enabled; }
    public void setEnabled(Integer enabled) { this.enabled = enabled; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}