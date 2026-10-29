package com.ragstudy.security;

import com.ragstudy.model.entity.AuditLog;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.repository.AuditLogMapper;
import com.ragstudy.repository.SysUserMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.UUID;

/**
 * 管理台写操作审计拦截器。
 *
 * 审计与系统日志的区别在于"谁在什么时间对什么做了什么"——此前只有登录事件入库，
 * 管理台的大量写操作（用户/角色/菜单/知识库/安全规则/配置/密钥）不留痕，审计
 * 退化为第二份系统日志。这里统一拦截 /api/admin、/api/system、/api/security 下的
 * 非幂等请求，成功失败都记一条，操作人从 SecurityContext 还原。
 */
@Component
public class AdminAuditInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(AdminAuditInterceptor.class);

    private final AuditLogMapper auditLogMapper;
    private final SysUserMapper sysUserMapper;

    public AdminAuditInterceptor(AuditLogMapper auditLogMapper, SysUserMapper sysUserMapper) {
        this.auditLogMapper = auditLogMapper;
        this.sysUserMapper = sysUserMapper;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        String method = request.getMethod();
        if ("GET".equalsIgnoreCase(method) || "HEAD".equalsIgnoreCase(method) || "OPTIONS".equalsIgnoreCase(method)) {
            return;
        }
        try {
            AuditLog audit = new AuditLog();
            // operation 用与既有审计一致的类别词（CREATE/UPDATE/DELETE），
            // 管理台"审计日志"页按此过滤；具体路径放 detail
            audit.setOperation(resolveOperation(method));
            audit.setTargetType(resolveTargetType(request.getRequestURI()));
            audit.setTargetId(lastSegment(request.getRequestURI()));
            audit.setDetail("管理台写操作: " + method + " " + request.getRequestURI()
                    + (request.getQueryString() != null ? "?" + request.getQueryString() : ""));
            boolean ok = response.getStatus() < 400 && ex == null;
            audit.setResult(ok ? "SUCCESS" : "FAIL");
            if (!ok) {
                audit.setErrorMsg("HTTP " + response.getStatus() + (ex != null ? " " + ex.getMessage() : ""));
            }
            audit.setIpAddress(request.getRemoteAddr());
            audit.setUserAgent(request.getHeader("User-Agent"));
            audit.setUniqueTag(UUID.randomUUID().toString());

            Long userId = currentUserId();
            audit.setUserId(userId);
            if (userId != null) {
                SysUser user = sysUserMapper.selectById(userId);
                audit.setUsername(user != null ? user.getUsername() : String.valueOf(userId));
            } else {
                audit.setUsername("anonymous");
            }
            auditLogMapper.insert(audit);
        } catch (Exception e) {
            // 审计失败不能阻断业务请求
            log.warn("管理台操作审计记录失败: {}", e.getMessage());
        }
    }

    private Long currentUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof Long userId) {
            return userId;
        }
        return null;
    }

    private String resolveOperation(String method) {
        return switch (method.toUpperCase()) {
            case "POST" -> "CREATE";
            case "PUT", "PATCH" -> "UPDATE";
            case "DELETE" -> "DELETE";
            default -> method.toUpperCase();
        };
    }

    /** /api/admin/users/57/roles → user（资源段取倒数第二段，末段多为 id 或子动作） */
    private String resolveTargetType(String uri) {
        String[] parts = uri.split("/");
        for (int i = parts.length - 1; i >= 1; i--) {
            if (parts[i].matches("\\d+")) {
                return i - 1 > 0 ? parts[i - 1] : parts[i];
            }
        }
        return parts.length > 1 ? parts[parts.length - 1] : uri;
    }

    private String lastSegment(String uri) {
        String[] parts = uri.split("/");
        return parts.length > 0 ? parts[parts.length - 1] : "";
    }
}
