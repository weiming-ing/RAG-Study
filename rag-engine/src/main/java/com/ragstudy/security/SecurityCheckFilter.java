package com.ragstudy.security;

import com.ragstudy.model.entity.ApiKey;
import com.ragstudy.service.AccessControlService;
import com.ragstudy.service.ApiKeyService;
import com.ragstudy.service.RateLimitService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * 安全校验过滤器：IP 访问控制 + API Key 鉴权 + API 限流
 *
 * 执行顺序：InternalApiAuthFilter → SecurityCheckFilter → JwtAuthFilter → UsernamePasswordAuthenticationFilter
 *
 * 校验规则：
 *   1. IP 黑名单命中 → 403 Forbidden
 *   2. IP 白名单命中 → 直接放行（跳过限流）
 *   3. API Key 鉴权：X-API-Key 请求头存在时，校验有效性，有效则注入认证上下文
 *   4. USER 维度限流 → 基于请求 IP 的令牌桶，触发则 429 Too Many Requests
 *   5. ENDPOINT 维度限流 → 基于请求路径的令牌桶
 */
@Component
public class SecurityCheckFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(SecurityCheckFilter.class);

    private final AccessControlService accessControlService;
    private final RateLimitService rateLimitService;
    private final ApiKeyService apiKeyService;

    public SecurityCheckFilter(AccessControlService accessControlService,
                               RateLimitService rateLimitService,
                               ApiKeyService apiKeyService) {
        this.accessControlService = accessControlService;
        this.rateLimitService = rateLimitService;
        this.apiKeyService = apiKeyService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String clientIp = getClientIp(request);
        String requestPath = request.getRequestURI();

        // 1. 黑名单检查
        if (accessControlService.isBlocked(clientIp, null, null)) {
            log.warn("IP {} 在黑名单中，拒绝访问 {}", clientIp, requestPath);
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(
                    "{\"code\":403,\"message\":\"Access denied: IP is blocked\",\"data\":null}");
            return;
        }

        // 2. 白名单检查（白名单 IP 跳过后续所有检查）
        if (accessControlService.isWhitelisted(clientIp)) {
            log.debug("IP {} 在白名单中，跳过限流检查", clientIp);
            filterChain.doFilter(request, response);
            return;
        }

        // 3. API Key 鉴权（X-API-Key 请求头）
        String apiKeyHeader = request.getHeader("X-API-Key");
        if (apiKeyHeader != null && !apiKeyHeader.isBlank()) {
            ApiKey keyEntity = apiKeyService.validate(apiKeyHeader);
            if (keyEntity == null || keyEntity.getEnabled() == null || keyEntity.getEnabled() != 1) {
                log.warn("API Key 无效或已禁用: {}", apiKeyHeader.substring(0, Math.min(8, apiKeyHeader.length())));
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                response.setContentType("application/json;charset=UTF-8");
                response.getWriter().write(
                        "{\"code\":401,\"message\":\"Invalid or disabled API key\",\"data\":null}");
                return;
            }

            // 检查 API Key 自带的调用量限制
            if (keyEntity.getDailyLimit() != null && keyEntity.getDailyLimit() > 0
                    && keyEntity.getTotalCalls() != null
                    && keyEntity.getTotalCalls() >= keyEntity.getDailyLimit()) {
                log.warn("API Key 已达日调用上限: {} calls", keyEntity.getTotalCalls());
                response.setStatus(429);
                response.setContentType("application/json;charset=UTF-8");
                response.getWriter().write(
                        "{\"code\":429,\"message\":\"API key daily limit exceeded\",\"data\":null}");
                return;
            }

            // API Key 有效，注入认证上下文
            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(
                            keyEntity.getUserId(), null,
                            List.of(new SimpleGrantedAuthority("ROLE_API_KEY")));
            authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
            SecurityContextHolder.getContext().setAuthentication(authentication);

            // 记录调用
            try {
                apiKeyService.recordUsage(apiKeyHeader);
            } catch (Exception e) {
                log.warn("记录 API Key 调用失败: {}", e.getMessage());
            }

            filterChain.doFilter(request, response);
            return;
        }

        // 4. USER 维度限流（按 IP 统计）
        if (!rateLimitService.checkLimit("USER", clientIp, requestPath)) {
            log.warn("IP {} 触发用户维度限流 {}", clientIp, requestPath);
            response.setStatus(429);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(
                    "{\"code\":429,\"message\":\"Rate limit exceeded\",\"data\":null}");
            return;
        }

        // 5. ENDPOINT 维度限流（按请求路径统计）
        if (!rateLimitService.checkLimit("ENDPOINT", requestPath, requestPath)) {
            log.warn("路径 {} 触终端点维度限流", requestPath);
            response.setStatus(429);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(
                    "{\"code\":429,\"message\":\"Rate limit exceeded\",\"data\":null}");
            return;
        }

        filterChain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/api/internal/")
                || path.startsWith("/api/auth/")
                || path.startsWith("/actuator/health");
    }

    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip != null && !ip.isBlank() && !"unknown".equalsIgnoreCase(ip)) {
            return ip.split(",")[0].trim();
        }
        ip = request.getHeader("X-Real-IP");
        if (ip != null && !ip.isBlank() && !"unknown".equalsIgnoreCase(ip)) {
            return ip;
        }
        return request.getRemoteAddr();
    }
}