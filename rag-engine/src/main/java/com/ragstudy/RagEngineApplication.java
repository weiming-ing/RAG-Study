package com.ragstudy;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

@SpringBootApplication
@EnableCaching
public class RagEngineApplication {

    public static void main(String[] args) {
        SpringApplication.run(RagEngineApplication.class, args);
    }
}