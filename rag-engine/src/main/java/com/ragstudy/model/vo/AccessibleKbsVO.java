package com.ragstudy.model.vo;

import java.util.List;

/**
 * 用户可访问的知识库集合（三级可见级别解析结果）
 *
 * kbIds：用户可检索/可见的知识库 id 全集
 * isAdmin：是否 ROLE_ADMIN（管理员可见全部）
 */
public class AccessibleKbsVO {

    private List<Long> kbIds;
    private boolean isAdmin;

    public List<Long> getKbIds() { return kbIds; }
    public void setKbIds(List<Long> kbIds) { this.kbIds = kbIds; }
    public boolean getIsAdmin() { return isAdmin; }
    public void setIsAdmin(boolean isAdmin) { this.isAdmin = isAdmin; }
}
