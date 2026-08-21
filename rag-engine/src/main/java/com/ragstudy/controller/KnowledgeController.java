package com.ragstudy.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.vo.DocumentVO;
import com.ragstudy.model.vo.KnowledgeStatsVO;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.service.KnowledgeBaseService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/internal/knowledge")
public class KnowledgeController {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeController.class);

    private final KnowledgeBaseService knowledgeBaseService;

    public KnowledgeController(KnowledgeBaseService knowledgeBaseService) {
        this.knowledgeBaseService = knowledgeBaseService;
    }

    @PostMapping("/upload")
    public ApiResponse<DocumentVO> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "department", required = false) String department,
            @RequestParam(value = "category", required = false) String category) {

        log.info("收到文档上传请求: fileName={}, department={}, category={}",
                file.getOriginalFilename(), department, category);

        DocumentVO document = knowledgeBaseService.uploadDocument(file, department, category);
        return ApiResponse.success(document);
    }

    @GetMapping("/list")
    public ApiResponse<Page<DocumentVO>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String department,
            @RequestParam(required = false) String category) {

        Page<DocumentVO> page = knowledgeBaseService.listDocuments(pageNum, pageSize, department, category);
        return ApiResponse.success(page);
    }

    @DeleteMapping("/{documentId}")
    public ApiResponse<Void> delete(@PathVariable String documentId) {
        knowledgeBaseService.deleteDocument(documentId);
        return ApiResponse.success();
    }

    @GetMapping("/{documentId}")
    public ApiResponse<DocumentVO> getById(@PathVariable String documentId) {
        log.info("获取文档详情: id={}", documentId);
        DocumentVO document = knowledgeBaseService.getDocumentById(documentId);
        return ApiResponse.success(document);
    }

    @GetMapping("/statistics")
    public ApiResponse<KnowledgeStatsVO> statistics() {
        KnowledgeStatsVO stats = knowledgeBaseService.getStatistics();
        return ApiResponse.success(stats);
    }

    @GetMapping("/chunks/{documentId}")
    public ApiResponse<List<KnowledgeChunk>> getChunks(@PathVariable String documentId) {
        log.info("获取文档分块: documentId={}", documentId);
        List<KnowledgeChunk> chunks = knowledgeBaseService.getChunksByDocumentId(documentId);
        return ApiResponse.success(chunks);
    }

    @GetMapping("/chunk/{chunkId}")
    public ApiResponse<KnowledgeChunk> getChunkById(@PathVariable String chunkId) {
        log.info("获取单个分块: chunkId={}", chunkId);
        KnowledgeChunk chunk = knowledgeBaseService.getChunkByChunkId(chunkId);
        if (chunk == null) {
            return ApiResponse.error(404, "分块不存在");
        }
        return ApiResponse.success(chunk);
    }

    @PutMapping("/chunks/{chunkId}")
    public ApiResponse<Void> updateChunk(
            @PathVariable String chunkId,
            @RequestBody Map<String, String> body) {
        String content = body.get("content");
        if (content == null || content.isBlank()) {
            return ApiResponse.error(400, "内容不能为空");
        }
        log.info("更新分块: chunkId={}, contentLength={}", chunkId, content.length());
        knowledgeBaseService.updateChunk(chunkId, content);
        return ApiResponse.success();
    }
}