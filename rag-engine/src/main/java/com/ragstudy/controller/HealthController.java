package com.ragstudy.controller;

import com.ragstudy.common.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.Map;

@RestController
@RequestMapping("/api/internal")
public class HealthController {

    @GetMapping("/health")
    public ApiResponse<Map<String, Object>> health() {
        Map<String, Object> info = Map.of(
                "status", "UP",
                "service", "rag-engine",
                "version", "1.0.0",
                "timestamp", LocalDateTime.now().toString()
        );
        return ApiResponse.success(info);
    }
}