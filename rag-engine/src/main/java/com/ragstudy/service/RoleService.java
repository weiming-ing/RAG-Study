package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ragstudy.common.BusinessException;
import com.ragstudy.model.dto.AssignRoleMenusRequest;
import com.ragstudy.model.dto.RoleCreateRequest;
import com.ragstudy.model.entity.SysRole;
import com.ragstudy.model.entity.SysRoleMenu;
import com.ragstudy.model.vo.RoleVO;
import com.ragstudy.repository.SysRoleMapper;
import com.ragstudy.repository.SysRoleMenuMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class RoleService {

    private final SysRoleMapper sysRoleMapper;
    private final SysRoleMenuMapper sysRoleMenuMapper;

    public RoleService(SysRoleMapper sysRoleMapper, SysRoleMenuMapper sysRoleMenuMapper) {
        this.sysRoleMapper = sysRoleMapper;
        this.sysRoleMenuMapper = sysRoleMenuMapper;
    }

    public List<RoleVO> listRoles() {
        List<SysRole> roles = sysRoleMapper.selectList(null);
        return roles.stream().map(role -> {
            RoleVO vo = new RoleVO();
            vo.setId(role.getId());
            vo.setRoleName(role.getRoleName());
            vo.setRoleCode(role.getRoleCode());
            vo.setDescription(role.getDescription());
            vo.setMenuIds(sysRoleMenuMapper.selectMenuIdsByRoleId(role.getId()));
            vo.setCreateTime(role.getCreateTime());
            return vo;
        }).collect(Collectors.toList());
    }

    public RoleVO getRoleById(Long id) {
        SysRole role = sysRoleMapper.selectById(id);
        if (role == null) {
            throw new BusinessException("角色不存在");
        }
        RoleVO vo = new RoleVO();
        vo.setId(role.getId());
        vo.setRoleName(role.getRoleName());
        vo.setRoleCode(role.getRoleCode());
        vo.setDescription(role.getDescription());
        vo.setMenuIds(sysRoleMenuMapper.selectMenuIdsByRoleId(role.getId()));
        vo.setCreateTime(role.getCreateTime());
        return vo;
    }

    @Transactional
    public RoleVO createRole(RoleCreateRequest request) {
        Long count = sysRoleMapper.selectCount(
                new LambdaQueryWrapper<SysRole>().eq(SysRole::getRoleCode, request.getRoleCode())
        );
        if (count > 0) {
            throw new BusinessException("角色编码已存在");
        }
        SysRole role = new SysRole();
        role.setRoleName(request.getRoleName());
        role.setRoleCode(request.getRoleCode());
        role.setDescription(request.getDescription());
        sysRoleMapper.insert(role);

        return getRoleById(role.getId());
    }

    @Transactional
    public RoleVO updateRole(Long id, RoleCreateRequest request) {
        SysRole role = sysRoleMapper.selectById(id);
        if (role == null) {
            throw new BusinessException("角色不存在");
        }
        if (request.getRoleName() != null) role.setRoleName(request.getRoleName());
        if (request.getDescription() != null) role.setDescription(request.getDescription());
        sysRoleMapper.updateById(role);

        return getRoleById(id);
    }

    @Transactional
    public void deleteRole(Long id) {
        SysRole role = sysRoleMapper.selectById(id);
        if (role == null) {
            throw new BusinessException("角色不存在");
        }
        sysRoleMapper.deleteById(id);
        sysRoleMenuMapper.delete(new LambdaQueryWrapper<SysRoleMenu>().eq(SysRoleMenu::getRoleId, id));
    }

    @Transactional
    public void assignMenus(Long roleId, AssignRoleMenusRequest request) {
        SysRole role = sysRoleMapper.selectById(roleId);
        if (role == null) {
            throw new BusinessException("角色不存在");
        }
        sysRoleMenuMapper.delete(new LambdaQueryWrapper<SysRoleMenu>().eq(SysRoleMenu::getRoleId, roleId));
        if (request.getMenuIds() != null && !request.getMenuIds().isEmpty()) {
            for (Long menuId : request.getMenuIds()) {
                SysRoleMenu roleMenu = new SysRoleMenu();
                roleMenu.setRoleId(roleId);
                roleMenu.setMenuId(menuId);
                sysRoleMenuMapper.insert(roleMenu);
            }
        }
    }
}