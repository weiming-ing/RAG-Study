package com.ragstudy.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 服务间接口（/api/internal/**）鉴权过滤器。
 *
 * 背景：/api/internal/** 供 Python 编排层与 MCP 服务调用，不走用户 JWT，
 * 此前在 SecurityConfig 中被 permitAll 放行，等于对可达网络完全开放
 * （可匿名检索知识库、读取切片、上传文档、触发重建）。
 *
 * 方案：要求请求携带 X-Internal-Token 头，其值与配置项 rag.internal.token 一致。
 * 该配置项无默认值（见 application.yml），未配置时 Java 启动即失败，
 * 不会静默降级为无鉴权；运行期令牌缺失或不匹配一律返回 401。
 */
@Component
public class InternalApiAuthFilter extends OncePerRequestFilter {

    private static final String HEADER_NAME = "X-Internal-Token";
    private static final String INTERNAL_PREFIX = "/api/internal";

    private final byte[] expectedToken;

    public InternalApiAuthFilter(@Value("${rag.internal.token}") String token) {
        this.expectedToken = token == null
                ? new byte[0]
                : token.trim().getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (!request.getRequestURI().startsWith(INTERNAL_PREFIX)) {
            filterChain.doFilter(request, response);
            return;
        }

        String provided = request.getHeader(HEADER_NAME);
        if (expectedToken.length > 0 && provided != null
                && MessageDigest.isEqual(provided.trim().getBytes(StandardCharsets.UTF_8), expectedToken)) {
            filterChain.doFilter(request, response);
            return;
        }

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(
                "{\"code\":401,\"message\":\"内部接口未授权：缺少或错误的 X-Internal-Token\",\"data\":null}");
    }
}
