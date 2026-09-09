package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.ResetPasswordRequest;
import com.ragstudy.model.dto.UserCreateRequest;
import com.ragstudy.model.dto.UserUpdateRequest;
import com.ragstudy.model.vo.UserVO;
import com.ragstudy.service.UserService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/admin/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping("/list")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<List<UserVO>> listAll() {
        return ApiResponse.success(userService.listAllUsers());
    }

    @GetMapping
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<IPage<UserVO>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status) {
        return ApiResponse.success(userService.listUsers(pageNum, pageSize, keyword, status));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<UserVO> getById(@PathVariable Long id) {
        return ApiResponse.success(userService.getUserById(id));
    }

    @PostMapping
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<UserVO> create(@RequestBody UserCreateRequest request) {
        return ApiResponse.success(userService.createUser(request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<UserVO> update(@PathVariable Long id, @RequestBody UserUpdateRequest request) {
        return ApiResponse.success(userService.updateUser(id, request));
    }

    @PutMapping("/{id}/status")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> updateStatus(@PathVariable Long id, @RequestBody Map<String, Integer> body) {
        Integer status = body.get("status");
        userService.updateStatus(id, status);
        return ApiResponse.success();
    }

    @PutMapping("/{id}/password")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> resetPassword(@PathVariable Long id, @RequestBody Map<String, String> body) {
        String password = body.getOrDefault("password", body.get("newPassword"));
        userService.resetPassword(id, password);
        return ApiResponse.success();
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        userService.deleteUser(id);
        return ApiResponse.success();
    }

    @PutMapping("/{id}/roles")
    @PreAuthorize("hasRole('ROLE_ADMIN')")
    public ApiResponse<Void> assignRoles(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Integer> rawIds = (List<Integer>) body.get("roleIds");
        List<Long> roleIds = rawIds.stream().map(Integer::longValue).toList();
        userService.assignRoles(id, roleIds);
        return ApiResponse.success();
    }
}