package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ragstudy.common.BusinessException;
import com.ragstudy.model.dto.MenuCreateRequest;
import com.ragstudy.model.entity.SysMenu;
import com.ragstudy.model.vo.MenuVO;
import com.ragstudy.repository.SysMenuMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class MenuService {

    private final SysMenuMapper sysMenuMapper;

    public MenuService(SysMenuMapper sysMenuMapper) {
        this.sysMenuMapper = sysMenuMapper;
    }

    public List<MenuVO> getMenuTree() {
        List<SysMenu> menus = sysMenuMapper.selectList(
                new LambdaQueryWrapper<SysMenu>().orderByAsc(SysMenu::getSortOrder)
        );
        return buildTree(menus, 0L);
    }

    public List<MenuVO> getUserMenus(Long userId) {
        List<SysMenu> menus = sysMenuMapper.selectMenusByUserId(userId);
        return buildTree(menus, 0L);
    }

    private List<MenuVO> buildTree(List<SysMenu> menus, Long parentId) {
        List<MenuVO> tree = new ArrayList<>();
        for (SysMenu menu : menus) {
            if (menu.getParentId().equals(parentId)) {
                MenuVO vo = toVO(menu);
                vo.setChildren(buildTree(menus, menu.getId()));
                tree.add(vo);
            }
        }
        return tree;
    }

    public MenuVO getMenuById(Long id) {
        SysMenu menu = sysMenuMapper.selectById(id);
        if (menu == null) {
            throw new BusinessException("菜单不存在");
        }
        return toVO(menu);
    }

    @Transactional
    public MenuVO createMenu(MenuCreateRequest request) {
        SysMenu menu = new SysMenu();
        menu.setParentId(request.getParentId() != null ? request.getParentId() : 0L);
        menu.setMenuName(request.getMenuName());
        menu.setMenuType(request.getMenuType() != null ? request.getMenuType() : "MENU");
        menu.setPath(request.getPath());
        menu.setComponent(request.getComponent());
        menu.setIcon(request.getIcon());
        menu.setSortOrder(request.getSortOrder() != null ? request.getSortOrder() : 0);
        menu.setPermissionCode(request.getPermissionCode());
        menu.setVisible(request.getVisible() != null ? request.getVisible() : 1);
        sysMenuMapper.insert(menu);

        return getMenuById(menu.getId());
    }

    @Transactional
    public MenuVO updateMenu(Long id, MenuCreateRequest request) {
        SysMenu menu = sysMenuMapper.selectById(id);
        if (menu == null) {
            throw new BusinessException("菜单不存在");
        }
        if (request.getMenuName() != null) menu.setMenuName(request.getMenuName());
        if (request.getMenuType() != null) menu.setMenuType(request.getMenuType());
        if (request.getPath() != null) menu.setPath(request.getPath());
        if (request.getComponent() != null) menu.setComponent(request.getComponent());
        if (request.getIcon() != null) menu.setIcon(request.getIcon());
        if (request.getSortOrder() != null) menu.setSortOrder(request.getSortOrder());
        if (request.getPermissionCode() != null) menu.setPermissionCode(request.getPermissionCode());
        if (request.getVisible() != null) menu.setVisible(request.getVisible());
        sysMenuMapper.updateById(menu);

        return getMenuById(id);
    }

    @Transactional
    public void deleteMenu(Long id) {
        Long count = sysMenuMapper.selectCount(
                new LambdaQueryWrapper<SysMenu>().eq(SysMenu::getParentId, id)
        );
        if (count > 0) {
            throw new BusinessException("存在子菜单，无法删除");
        }
        sysMenuMapper.deleteById(id);
    }

    private MenuVO toVO(SysMenu menu) {
        MenuVO vo = new MenuVO();
        vo.setId(menu.getId());
        vo.setParentId(menu.getParentId());
        vo.setMenuName(menu.getMenuName());
        vo.setMenuType(menu.getMenuType());
        vo.setPath(menu.getPath());
        vo.setComponent(menu.getComponent());
        vo.setIcon(menu.getIcon());
        vo.setSortOrder(menu.getSortOrder());
        vo.setPermissionCode(menu.getPermissionCode());
        vo.setVisible(menu.getVisible());
        vo.setCreateTime(menu.getCreateTime());
        return vo;
    }
}