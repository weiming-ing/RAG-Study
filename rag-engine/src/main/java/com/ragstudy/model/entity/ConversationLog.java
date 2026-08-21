package com.ragstudy.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import java.time.LocalDateTime;

@TableName("conversation_log")
public class ConversationLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String sessionId;
    private Long userId;
    private String question;
    private String answer;
    private String referencedChunks;
    private String kbId;
    private String status;
    private Integer feedback;
    private String feedbackComment;
    private String feedbackReason;
    private Integer latencyMs;
    private Integer tokenCount;
    private String ipAddress;

    @TableField(exist = false)
    private String username;

    @TableField(exist = false)
    private String kbName;

    private Integer totalCount;

    private String conversationData;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
    public String getReferencedChunks() { return referencedChunks; }
    public void setReferencedChunks(String referencedChunks) { this.referencedChunks = referencedChunks; }
    public String getKbId() { return kbId; }
    public void setKbId(String kbId) { this.kbId = kbId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Integer getFeedback() { return feedback; }
    public void setFeedback(Integer feedback) { this.feedback = feedback; }
    public String getFeedbackComment() { return feedbackComment; }
    public void setFeedbackComment(String feedbackComment) { this.feedbackComment = feedbackComment; }
    public String getFeedbackReason() { return feedbackReason; }
    public void setFeedbackReason(String feedbackReason) { this.feedbackReason = feedbackReason; }
    public Integer getLatencyMs() { return latencyMs; }
    public void setLatencyMs(Integer latencyMs) { this.latencyMs = latencyMs; }
    public Integer getTokenCount() { return tokenCount; }
    public void setTokenCount(Integer tokenCount) { this.tokenCount = tokenCount; }
    public String getIpAddress() { return ipAddress; }
    public void setIpAddress(String ipAddress) { this.ipAddress = ipAddress; }
    public Integer getTotalCount() { return totalCount; }
    public void setTotalCount(Integer totalCount) { this.totalCount = totalCount; }
    public String getConversationData() { return conversationData; }
    public void setConversationData(String conversationData) { this.conversationData = conversationData; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getKbName() { return kbName; }
    public void setKbName(String kbName) { this.kbName = kbName; }
}