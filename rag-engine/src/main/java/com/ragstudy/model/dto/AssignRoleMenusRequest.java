package com.ragstudy.model.dto;

import java.util.List;

public class AssignRoleMenusRequest {

    private List<Long> menuIds;

    public List<Long> getMenuIds() { return menuIds; }
    public void setMenuIds(List<Long> menuIds) { this.menuIds = menuIds; }
}