package com.ragstudy.model.dto;

import java.util.List;

public class KbAccessRequest {

    private List<Long> userIds;
    private String accessLevel;

    public List<Long> getUserIds() { return userIds; }
    public void setUserIds(List<Long> userIds) { this.userIds = userIds; }
    public String getAccessLevel() { return accessLevel; }
    public void setAccessLevel(String accessLevel) { this.accessLevel = accessLevel; }
}