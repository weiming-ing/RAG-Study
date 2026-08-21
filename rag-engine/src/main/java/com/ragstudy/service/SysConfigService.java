package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.SysConfig;
import com.ragstudy.repository.SysConfigMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.stream.Collectors;

@Service
public class SysConfigService {

    private final SysConfigMapper sysConfigMapper;

    public SysConfigService(SysConfigMapper sysConfigMapper) {
        this.sysConfigMapper = sysConfigMapper;
    }

    @Cacheable(value = "sysConfig", key = "#key")
    public String getConfigValue(String key) {
        SysConfig config = sysConfigMapper.findByKey(key);
        return config != null ? config.getConfigValue() : null;
    }

    public String getConfigValue(String key, String defaultValue) {
        String value = getConfigValue(key);
        return value != null ? value : defaultValue;
    }

    public Integer getConfigInt(String key, Integer defaultValue) {
        String value = getConfigValue(key);
        try {
            return value != null ? Integer.parseInt(value) : defaultValue;
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public Boolean getConfigBoolean(String key, Boolean defaultValue) {
        String value = getConfigValue(key);
        if (value == null) return defaultValue;
        return "true".equalsIgnoreCase(value) || "1".equals(value);
    }

    public Map<String, Object> getConfigByGroup(String group) {
        List<SysConfig> configs = sysConfigMapper.findByGroup(group);
        Map<String, Object> result = new LinkedHashMap<>();
        for (SysConfig config : configs) {
            result.put(config.getConfigKey(), convertValue(config.getConfigValue(), config.getConfigType()));
        }
        return result;
    }

    public Map<String, Object> getAllConfigsGrouped() {
        List<SysConfig> allConfigs = sysConfigMapper.selectList(
            new QueryWrapper<SysConfig>().eq("enabled", 1).orderByAsc("sort_order")
        );
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, List<SysConfig>> grouped = allConfigs.stream()
            .collect(Collectors.groupingBy(SysConfig::getConfigGroup, LinkedHashMap::new, Collectors.toList()));
        for (Map.Entry<String, List<SysConfig>> entry : grouped.entrySet()) {
            Map<String, Object> groupConfigs = new LinkedHashMap<>();
            for (SysConfig config : entry.getValue()) {
                groupConfigs.put(config.getConfigKey(), convertValue(config.getConfigValue(), config.getConfigType()));
            }
            result.put(entry.getKey(), groupConfigs);
        }
        return result;
    }

    public Map<String, Object> listConfigs(String group, String keyword, int page, int size) {
        QueryWrapper<SysConfig> wrapper = new QueryWrapper<>();
        if (group != null && !group.isEmpty()) {
            wrapper.eq("config_group", group);
        }
        if (keyword != null && !keyword.isEmpty()) {
            wrapper.and(w -> w.like("config_key", keyword).or().like("description", keyword));
        }
        wrapper.orderByAsc("config_group", "sort_order");

        Page<SysConfig> pageResult = sysConfigMapper.selectPage(new Page<>(page, size), wrapper);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("records", pageResult.getRecords());
        result.put("total", pageResult.getTotal());
        result.put("page", pageResult.getCurrent());
        result.put("size", pageResult.getSize());
        return result;
    }

    @Transactional
    @CacheEvict(value = "sysConfig", key = "#config.configKey")
    public SysConfig saveConfig(SysConfig config) {
        if (config.getId() != null) {
            sysConfigMapper.updateById(config);
        } else {
            sysConfigMapper.insert(config);
        }
        return config;
    }

    @Transactional
    @CacheEvict(value = "sysConfig", allEntries = true)
    public SysConfig updateConfig(Long id, SysConfig config) {
        config.setId(id);
        sysConfigMapper.updateById(config);
        return sysConfigMapper.selectById(id);
    }

    @Transactional
    @CacheEvict(value = "sysConfig", allEntries = true)
    public void deleteConfig(Long id) {
        sysConfigMapper.deleteById(id);
    }

    @Transactional
    @CacheEvict(value = "sysConfig", allEntries = true)
    public int batchUpdateConfigs(List<Map<String, String>> configs) {
        int count = 0;
        for (Map<String, String> item : configs) {
            String key = item.get("configKey");
            String value = item.get("configValue");
            if (key != null && value != null) {
                SysConfig config = sysConfigMapper.findByKey(key);
                if (config != null) {
                    config.setConfigValue(value);
                    sysConfigMapper.updateById(config);
                    count++;
                }
            }
        }
        return count;
    }

    public List<Map<String, Object>> getGroupStats() {
        return sysConfigMapper.getGroupStats();
    }

    private Object convertValue(String value, String type) {
        if (value == null) return null;
        switch (type != null ? type.toUpperCase() : "STRING") {
            case "NUMBER":
                try { return Double.parseDouble(value); } catch (NumberFormatException e) { return value; }
            case "BOOLEAN":
                return "true".equalsIgnoreCase(value) || "1".equals(value);
            case "JSON":
                try {
                    com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
                    return mapper.readTree(value);
                } catch (Exception e) { return value; }
            default:
                return value;
        }
    }
}