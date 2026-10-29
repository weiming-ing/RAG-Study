package com.ragstudy.config;

import com.ragstudy.security.AdminAuditInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 管理域写操作的审计拦截范围。/api/admin、/api/system、/api/security 覆盖
 * 用户/角色/菜单/配置/日志/敏感词/限流/访问控制/密钥；知识库与文档写操作在
 * Python 侧落审计（见 backend/routes/knowledge.py 的 _record_audit）。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final AdminAuditInterceptor adminAuditInterceptor;

    public WebMvcConfig(AdminAuditInterceptor adminAuditInterceptor) {
        this.adminAuditInterceptor = adminAuditInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(adminAuditInterceptor)
                .addPathPatterns("/api/admin/**", "/api/system/**", "/api/security/**");
    }
}
