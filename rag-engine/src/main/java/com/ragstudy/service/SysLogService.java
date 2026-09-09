package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.SysLog;
import com.ragstudy.repository.SysLogMapper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class SysLogService {

    private final SysLogMapper sysLogMapper;

    public SysLogService(SysLogMapper sysLogMapper) {
        this.sysLogMapper = sysLogMapper;
    }

    @Async
    public void log(String level, String module, String message, String detail,
                    Long userId, String username, String ipAddress, Long durationMs) {
        SysLog log = new SysLog();
        log.setLogLevel(level);
        log.setLogModule(module);
        log.setLogMessage(message);
        log.setLogDetail(detail);
        log.setTraceId(UUID.randomUUID().toString().replace("-", "").substring(0, 16));
        log.setUserId(userId);
        log.setUsername(username);
        log.setIpAddress(ipAddress);
        log.setDurationMs(durationMs);
        sysLogMapper.insert(log);
    }

    @Async
    public void info(String module, String message) {
        log("INFO", module, message, null, null, null, null, null);
    }

    @Async
    public void warn(String module, String message) {
        log("WARN", module, message, null, null, null, null, null);
    }

    @Async
    public void error(String module, String message, String detail) {
        log("ERROR", module, message, detail, null, null, null, null);
    }

    public Map<String, Object> listLogs(String level, String module, String keyword, int page, int size) {
        QueryWrapper<SysLog> wrapper = new QueryWrapper<>();
        if (level != null && !level.isEmpty()) {
            wrapper.eq("log_level", level);
        }
        if (module != null && !module.isEmpty()) {
            wrapper.eq("log_module", module);
        }
        if (keyword != null && !keyword.isEmpty()) {
            wrapper.and(w -> w.like("log_message", keyword).or().like("log_detail", keyword));
        }
        wrapper.orderByDesc("create_time");

        Page<SysLog> pageResult = sysLogMapper.selectPage(new Page<>(page, size), wrapper);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("records", pageResult.getRecords());
        result.put("total", pageResult.getTotal());
        result.put("page", pageResult.getCurrent());
        result.put("size", pageResult.getSize());
        return result;
    }

    public Map<String, Object> getLogStats(int days) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("byLevel", sysLogMapper.countByLevel(days));
        stats.put("byModule", sysLogMapper.countByModule(days));
        return stats;
    }

    @Transactional
    public int cleanExpiredLogs(int days) {
        return sysLogMapper.cleanExpired(days);
    }
}