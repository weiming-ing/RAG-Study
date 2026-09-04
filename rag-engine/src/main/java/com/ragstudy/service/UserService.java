package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.BusinessException;
import com.ragstudy.model.dto.UserCreateRequest;
import com.ragstudy.model.dto.UserUpdateRequest;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.model.entity.SysUserRole;
import com.ragstudy.model.vo.UserVO;
import com.ragstudy.repository.SysUserMapper;
import com.ragstudy.repository.SysUserRoleMapper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class UserService {

    private final SysUserMapper sysUserMapper;
    private final SysUserRoleMapper sysUserRoleMapper;
    private final PasswordEncoder passwordEncoder;

    public UserService(SysUserMapper sysUserMapper,
                       SysUserRoleMapper sysUserRoleMapper,
                       PasswordEncoder passwordEncoder) {
        this.sysUserMapper = sysUserMapper;
        this.sysUserRoleMapper = sysUserRoleMapper;
        this.passwordEncoder = passwordEncoder;
    }

    public IPage<UserVO> listUsers(int pageNum, int pageSize, String keyword, Integer status) {
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(SysUser::getUsername, keyword)
                    .or().like(SysUser::getDisplayName, keyword)
                    .or().like(SysUser::getEmail, keyword));
        }
        if (status != null) {
            wrapper.eq(SysUser::getStatus, status);
        }
        wrapper.orderByDesc(SysUser::getCreateTime);

        long total = sysUserMapper.selectCount(wrapper);
        long offset = (pageNum - 1L) * pageSize;
        wrapper.last("LIMIT " + offset + "," + pageSize);
        List<SysUser> users = sysUserMapper.selectList(wrapper);

        List<UserVO> voList = users.stream().map(user -> {
            UserVO vo = new UserVO();
            vo.setId(user.getId());
            vo.setUsername(user.getUsername());
            vo.setDisplayName(user.getDisplayName());
            vo.setEmail(user.getEmail());
            vo.setPhone(user.getPhone());
            vo.setAvatar(user.getAvatar());
            vo.setStatus(user.getStatus());
            vo.setRoles(sysUserMapper.selectRoleCodesByUserId(user.getId()));
            vo.setCreateTime(user.getCreateTime());
            vo.setUpdateTime(user.getUpdateTime());
            return vo;
        }).collect(Collectors.toList());

        Page<UserVO> result = new Page<>(pageNum, pageSize, total);
        result.setRecords(voList);
        return result;
    }

    public UserVO getUserById(Long id) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        UserVO vo = new UserVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setDisplayName(user.getDisplayName());
        vo.setEmail(user.getEmail());
        vo.setPhone(user.getPhone());
        vo.setAvatar(user.getAvatar());
        vo.setStatus(user.getStatus());
        vo.setRoles(sysUserMapper.selectRoleCodesByUserId(user.getId()));
        vo.setCreateTime(user.getCreateTime());
        vo.setUpdateTime(user.getUpdateTime());
        return vo;
    }

    @Transactional
    public UserVO createUser(UserCreateRequest request) {
        Long count = sysUserMapper.selectCount(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, request.getUsername())
        );
        if (count > 0) {
            throw new BusinessException("用户名已存在");
        }

        SysUser user = new SysUser();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setDisplayName(request.getDisplayName() != null ? request.getDisplayName() : request.getUsername());
        user.setEmail(request.getEmail());
        user.setPhone(request.getPhone());
        user.setStatus(request.getStatus() != null ? request.getStatus() : 1);
        sysUserMapper.insert(user);

        return getUserById(user.getId());
    }

    @Transactional
    public UserVO updateUser(Long id, UserUpdateRequest request) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        if (request.getDisplayName() != null) user.setDisplayName(request.getDisplayName());
        if (request.getEmail() != null) user.setEmail(request.getEmail());
        if (request.getPhone() != null) user.setPhone(request.getPhone());
        if (request.getStatus() != null) user.setStatus(request.getStatus());
        sysUserMapper.updateById(user);

        return getUserById(id);
    }

    @Transactional
    public void updateStatus(Long id, Integer status) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        user.setStatus(status);
        sysUserMapper.updateById(user);
    }

    @Transactional
    public void resetPassword(Long id, String newPassword) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        user.setPassword(passwordEncoder.encode(newPassword));
        sysUserMapper.updateById(user);
    }

    @Transactional
    public void deleteUser(Long id) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        sysUserMapper.deleteById(id);
        sysUserRoleMapper.delete(new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, id));
    }

    public List<UserVO> listAllUsers() {
        List<SysUser> users = sysUserMapper.selectList(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getStatus, 1).orderByDesc(SysUser::getCreateTime)
        );
        return users.stream().map(user -> {
            UserVO vo = new UserVO();
            vo.setId(user.getId());
            vo.setUsername(user.getUsername());
            vo.setDisplayName(user.getDisplayName());
            vo.setEmail(user.getEmail());
            vo.setPhone(user.getPhone());
            vo.setAvatar(user.getAvatar());
            vo.setStatus(user.getStatus());
            vo.setRoles(sysUserMapper.selectRoleCodesByUserId(user.getId()));
            vo.setCreateTime(user.getCreateTime());
            vo.setUpdateTime(user.getUpdateTime());
            return vo;
        }).collect(Collectors.toList());
    }

    public List<Long> getUserRoleIds(Long userId) {
        return sysUserRoleMapper.selectRoleIdsByUserId(userId);
    }

    @Transactional
    public void assignRoles(Long userId, List<Long> roleIds) {
        sysUserRoleMapper.delete(new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, userId));
        if (roleIds != null && !roleIds.isEmpty()) {
            for (Long roleId : roleIds) {
                SysUserRole userRole = new SysUserRole();
                userRole.setUserId(userId);
                userRole.setRoleId(roleId);
                sysUserRoleMapper.insert(userRole);
            }
        }
    }
}