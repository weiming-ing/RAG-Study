package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.SysConfig;
import com.ragstudy.repository.SysConfigMapper;
import com.ragstudy.service.SysConfigService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/system")
public class SysConfigController {

    private final SysConfigService sysConfigService;
    private final SysConfigMapper sysConfigMapper;

    public SysConfigController(SysConfigService sysConfigService, SysConfigMapper sysConfigMapper) {
        this.sysConfigService = sysConfigService;
        this.sysConfigMapper = sysConfigMapper;
    }

    @GetMapping("/configs")
    public ApiResponse<Map<String, Object>> listConfigs(
            @RequestParam(required = false) String group,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.success(sysConfigService.listConfigs(group, keyword, page, size));
    }

    @GetMapping("/configs/grouped")
    public ApiResponse<Map<String, Object>> getAllConfigsGrouped() {
        return ApiResponse.success(sysConfigService.getAllConfigsGrouped());
    }

    @GetMapping("/configs/group/{group}")
    public ApiResponse<Map<String, Object>> getConfigByGroup(@PathVariable String group) {
        return ApiResponse.success(sysConfigService.getConfigByGroup(group));
    }

    @GetMapping("/configs/{id}")
    public ApiResponse<SysConfig> getConfigById(@PathVariable Long id) {
        SysConfig config = sysConfigMapper.selectById(id);
        return config != null ? ApiResponse.success(config) : ApiResponse.error(404, "配置不存在");
    }

    @PostMapping("/configs")
    public ApiResponse<SysConfig> saveConfig(@RequestBody SysConfig config) {
        return ApiResponse.success(sysConfigService.saveConfig(config));
    }

    @PutMapping("/configs/{id}")
    public ApiResponse<SysConfig> updateConfig(@PathVariable Long id, @RequestBody SysConfig config) {
        return ApiResponse.success(sysConfigService.updateConfig(id, config));
    }

    @PutMapping("/configs/batch")
    public ApiResponse<Map<String, Object>> batchUpdateConfigs(@RequestBody List<Map<String, String>> configs) {
        int count = sysConfigService.batchUpdateConfigs(configs);
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("updatedCount", count);
        return ApiResponse.success(result);
    }

    @DeleteMapping("/configs/{id}")
    public ApiResponse<String> deleteConfig(@PathVariable Long id) {
        sysConfigService.deleteConfig(id);
        return ApiResponse.success("删除成功");
    }

    @GetMapping("/configs/stats")
    public ApiResponse<List<Map<String, Object>>> getGroupStats() {
        return ApiResponse.success(sysConfigService.getGroupStats());
    }
}