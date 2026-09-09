package com.ragstudy.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ragstudy.model.entity.SysUser;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface SysUserMapper extends BaseMapper<SysUser> {

    @Select("SELECT DISTINCT r.role_code FROM sys_user_role ur " +
            "JOIN sys_role r ON ur.role_id = r.id " +
            "WHERE ur.user_id = #{userId}")
    List<String> selectRoleCodesByUserId(@Param("userId") Long userId);

    @Select("SELECT DISTINCT m.permission_code FROM sys_role_menu rm " +
            "JOIN sys_menu m ON rm.menu_id = m.id " +
            "JOIN sys_user_role ur ON ur.role_id = rm.role_id " +
            "WHERE ur.user_id = #{userId} AND m.permission_code IS NOT NULL AND m.permission_code != ''")
    List<String> selectPermissionCodesByUserId(@Param("userId") Long userId);
}