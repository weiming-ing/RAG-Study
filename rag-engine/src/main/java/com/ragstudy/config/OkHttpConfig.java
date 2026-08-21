package com.ragstudy.config;

// OkHttpClient 用于调用LLM API，属于Python前端(API Gateway + LLM编排层)的职责
// Java后端仅负责知识库引擎层（文档管理、向量检索、BM25索引、重排序）
// 如需启用，取消下方注释

/*
import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

@Configuration
public class OkHttpConfig {

    @Bean
    public OkHttpClient okHttpClient() {
        return new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(600, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .connectionPool(new ConnectionPool(20, 5, TimeUnit.MINUTES))
                .retryOnConnectionFailure(true)
                .build();
    }
}
*/