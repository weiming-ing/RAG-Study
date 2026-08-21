package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.LoginRequest;
import com.ragstudy.model.dto.RegisterRequest;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.model.entity.SysUserRole;
import com.ragstudy.model.vo.LoginVO;
import com.ragstudy.model.vo.UserInfoVO;
import com.ragstudy.repository.SysUserMapper;
import com.ragstudy.repository.SysUserRoleMapper;
import com.ragstudy.security.JwtTokenProvider;
import com.ragstudy.security.SecurityUtils;
import jakarta.validation.Valid;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider jwtTokenProvider;
    private final PasswordEncoder passwordEncoder;
    private final SysUserMapper sysUserMapper;
    private final SysUserRoleMapper sysUserRoleMapper;

    public AuthController(AuthenticationManager authenticationManager,
                          JwtTokenProvider jwtTokenProvider,
                          PasswordEncoder passwordEncoder,
                          SysUserMapper sysUserMapper,
                          SysUserRoleMapper sysUserRoleMapper) {
        this.authenticationManager = authenticationManager;
        this.jwtTokenProvider = jwtTokenProvider;
        this.passwordEncoder = passwordEncoder;
        this.sysUserMapper = sysUserMapper;
        this.sysUserRoleMapper = sysUserRoleMapper;
    }

    @PostMapping("/login")
    public ApiResponse<LoginVO> login(@Valid @RequestBody LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.getUsername(), request.getPassword())
        );

        SysUser user = sysUserMapper.selectOne(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, request.getUsername())
        );

        String accessToken = jwtTokenProvider.generateAccessToken(user.getId(), user.getUsername());
        List<String> roleCodes = sysUserMapper.selectRoleCodesByUserId(user.getId());
        List<String> permissionCodes = sysUserMapper.selectPermissionCodesByUserId(user.getId());

        UserInfoVO userInfo = new UserInfoVO();
        userInfo.setId(user.getId());
        userInfo.setUsername(user.getUsername());
        userInfo.setDisplayName(user.getDisplayName());
        userInfo.setEmail(user.getEmail());
        userInfo.setPhone(user.getPhone());
        userInfo.setAvatar(user.getAvatar());
        userInfo.setStatus(user.getStatus());
        userInfo.setRoles(roleCodes != null ? roleCodes : Collections.emptyList());
        userInfo.setPermissions(permissionCodes != null ? permissionCodes : Collections.emptyList());

        LoginVO loginVO = LoginVO.builder()
                .accessToken(accessToken)
                .expiresIn(86400000L)
                .userInfo(userInfo)
                .build();

        return ApiResponse.success(loginVO);
    }

    @PostMapping("/register")
    public ApiResponse<Void> register(@Valid @RequestBody RegisterRequest request) {
        // 检查用户名是否已存在
        Long count = sysUserMapper.selectCount(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, request.getUsername())
        );
        if (count > 0) {
            return ApiResponse.error(400, "用户名已存在");
        }

        SysUser user = new SysUser();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setDisplayName(request.getDisplayName() != null ? request.getDisplayName() : request.getUsername());
        user.setStatus(1);
        sysUserMapper.insert(user);

        return ApiResponse.success();
    }

    @GetMapping("/me")
    public ApiResponse<UserInfoVO> me() {
        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            return ApiResponse.error(401, "未登录");
        }

        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            return ApiResponse.error(404, "用户不存在");
        }

        List<String> roleCodes = sysUserMapper.selectRoleCodesByUserId(user.getId());
        List<String> permissionCodes = sysUserMapper.selectPermissionCodesByUserId(user.getId());

        UserInfoVO userInfo = new UserInfoVO();
        userInfo.setId(user.getId());
        userInfo.setUsername(user.getUsername());
        userInfo.setDisplayName(user.getDisplayName());
        userInfo.setEmail(user.getEmail());
        userInfo.setPhone(user.getPhone());
        userInfo.setAvatar(user.getAvatar());
        userInfo.setStatus(user.getStatus());
        userInfo.setRoles(roleCodes != null ? roleCodes : Collections.emptyList());
        userInfo.setPermissions(permissionCodes != null ? permissionCodes : Collections.emptyList());

        return ApiResponse.success(userInfo);
    }
}