package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.MenuCreateRequest;
import com.ragstudy.model.vo.MenuVO;
import com.ragstudy.security.SecurityUtils;
import com.ragstudy.service.MenuService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/admin/menus")
public class MenuController {

    private final MenuService menuService;

    public MenuController(MenuService menuService) {
        this.menuService = menuService;
    }

    @GetMapping("/tree")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<List<MenuVO>> tree() {
        return ApiResponse.success(menuService.getMenuTree());
    }

    @GetMapping("/user")
    public ApiResponse<List<MenuVO>> userMenus() {
        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            return ApiResponse.success(Collections.emptyList());
        }
        return ApiResponse.success(menuService.getUserMenus(userId));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<MenuVO> getById(@PathVariable Long id) {
        return ApiResponse.success(menuService.getMenuById(id));
    }

    @PostMapping
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<MenuVO> create(@RequestBody MenuCreateRequest request) {
        return ApiResponse.success(menuService.createMenu(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<MenuVO> update(@PathVariable Long id, @RequestBody MenuCreateRequest request) {
        return ApiResponse.success(menuService.updateMenu(id, request));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        menuService.deleteMenu(id);
        return ApiResponse.success();
    }
}