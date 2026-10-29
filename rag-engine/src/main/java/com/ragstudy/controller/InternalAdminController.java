package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.ApiKey;
import com.ragstudy.model.entity.KbUserAccess;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.repository.KbUserAccessMapper;
import com.ragstudy.repository.SysUserMapper;
import com.ragstudy.service.ApiKeyService;
import com.ragstudy.service.SysConfigService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 内部管理接口（供 Python 网关调用，走 X-Internal-Token 门禁）
 *
 * 三条链路：
 *  1. API Key 校验——员工聊天页之外的开放 API 调用方携带 X-API-Key 直达 Python，
 *     Python 无法读库校验，转发到这里完成 有效期/禁用/限额 判定并回填调用次数；
 *  2. sys_config 读取——管理台"系统配置"页改的参数要被 Python 聊天链路真实消费；
 *  3. 用户已授权知识库——用户管理编辑弹窗回显某用户被授权的管理级知识库。
 */
@RestController
@RequestMapping("/api/internal/admin")
public class InternalAdminController {

    private final ApiKeyService apiKeyService;
    private final SysConfigService sysConfigService;
    private final KbUserAccessMapper kbUserAccessMapper;
    private final SysUserMapper sysUserMapper;

    public InternalAdminController(ApiKeyService apiKeyService,
                                   SysConfigService sysConfigService,
                                   KbUserAccessMapper kbUserAccessMapper,
                                   SysUserMapper sysUserMapper) {
        this.apiKeyService = apiKeyService;
        this.sysConfigService = sysConfigService;
        this.kbUserAccessMapper = kbUserAccessMapper;
        this.sysUserMapper = sysUserMapper;
    }

    @GetMapping("/api-key/validate")
    public ApiResponse<Map<String, Object>> validateApiKey(@RequestParam("apiKey") String apiKey) {
        ApiKey key = apiKeyService.validate(apiKey);
        if (key == null || key.getEnabled() == null || key.getEnabled() != 1) {
            return ApiResponse.success(Map.of("valid", false));
        }
        // 与 Java 直连路径（SecurityCheckFilter）保持一致：有效即计一次调用
        apiKeyService.recordUsage(apiKey);

        String username = null;
        if (key.getUserId() != null) {
            SysUser user = sysUserMapper.selectById(key.getUserId());
            username = user != null ? user.getUsername() : null;
        }
        return ApiResponse.success(Map.of(
                "valid", true,
                "userId", key.getUserId() != null ? key.getUserId() : 0L,
                "username", username != null ? username : ("api-key:" + key.getKeyName()),
                "keyName", key.getKeyName() != null ? key.getKeyName() : ""));
    }

    @GetMapping("/sys-config")
    public ApiResponse<Map<String, Object>> getSysConfig(@RequestParam("key") String key) {
        String value = sysConfigService.getConfigValue(key);
        return ApiResponse.success(Map.of("key", key, "value", value != null ? value : ""));
    }

    @GetMapping("/users/{userId}/managed-kbs")
    public ApiResponse<Map<String, Object>> managedKbs(@PathVariable Long userId) {
        List<Long> kbIds = kbUserAccessMapper.selectList(
                        new LambdaQueryWrapper<KbUserAccess>().eq(KbUserAccess::getUserId, userId))
                .stream().map(KbUserAccess::getKbId).distinct().toList();
        return ApiResponse.success(Map.of("kbIds", kbIds));
    }
}
