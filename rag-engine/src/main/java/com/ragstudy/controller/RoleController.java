package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.AssignRoleMenusRequest;
import com.ragstudy.model.dto.RoleCreateRequest;
import com.ragstudy.model.vo.RoleVO;
import com.ragstudy.service.RoleService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/admin/roles")
public class RoleController {

    private final RoleService roleService;

    public RoleController(RoleService roleService) {
        this.roleService = roleService;
    }

    @GetMapping
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<List<RoleVO>> list() {
        return ApiResponse.success(roleService.listRoles());
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<RoleVO> getById(@PathVariable Long id) {
        return ApiResponse.success(roleService.getRoleById(id));
    }

    @PostMapping
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<RoleVO> create(@RequestBody RoleCreateRequest request) {
        return ApiResponse.success(roleService.createRole(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<RoleVO> update(@PathVariable Long id, @RequestBody RoleCreateRequest request) {
        return ApiResponse.success(roleService.updateRole(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        roleService.deleteRole(id);
        return ApiResponse.success();
    }

    @PutMapping("/{id}/menus")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> assignMenus(@PathVariable Long id, @RequestBody AssignRoleMenusRequest request) {
        roleService.assignMenus(id, request);
        return ApiResponse.success();
    }
}