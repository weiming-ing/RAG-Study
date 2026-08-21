package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.service.ChunkService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/chunks")
public class ChunkController {

    private static final Logger log = LoggerFactory.getLogger(ChunkController.class);

    private final ChunkService chunkService;

    public ChunkController(ChunkService chunkService) {
        this.chunkService = chunkService;
    }

    @GetMapping
    public ApiResponse<IPage<KnowledgeChunk>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String documentId,
            @RequestParam(required = false) String keyword) {
        return ApiResponse.success(chunkService.listChunks(pageNum, pageSize, documentId, keyword));
    }

    @GetMapping("/{chunkId}")
    public ApiResponse<KnowledgeChunk> getById(@PathVariable String chunkId) {
        KnowledgeChunk chunk = chunkService.getChunkByChunkId(chunkId);
        if (chunk == null) {
            return ApiResponse.error(404, "切片不存在");
        }
        return ApiResponse.success(chunk);
    }

    @PutMapping("/{chunkId}")
    public ApiResponse<Void> update(@PathVariable String chunkId, @RequestBody Map<String, String> body) {
        String content = body.get("content");
        if (content == null || content.isBlank()) {
            return ApiResponse.error(400, "内容不能为空");
        }
        chunkService.updateChunkContent(chunkId, content);
        return ApiResponse.success();
    }

    @PostMapping("/{chunkId}/split")
    public ApiResponse<KnowledgeChunk> split(@PathVariable String chunkId, @RequestBody Map<String, Integer> body) {
        Integer position = body.get("position");
        if (position == null || position <= 0) {
            return ApiResponse.error(400, "分割位置无效");
        }
        KnowledgeChunk newChunk = chunkService.splitChunk(chunkId, position);
        return ApiResponse.success(newChunk);
    }

    @PostMapping("/merge")
    public ApiResponse<KnowledgeChunk> merge(@RequestBody Map<String, String> body) {
        String chunkId1 = body.get("chunkId1");
        String chunkId2 = body.get("chunkId2");
        if (chunkId1 == null || chunkId2 == null) {
            return ApiResponse.error(400, "请提供两个切片ID");
        }
        KnowledgeChunk merged = chunkService.mergeChunks(chunkId1, chunkId2);
        return ApiResponse.success(merged);
    }

    @DeleteMapping("/{chunkId}")
    public ApiResponse<Void> delete(@PathVariable String chunkId) {
        chunkService.deleteChunkVector(chunkId);
        return ApiResponse.success();
    }

    @PostMapping("/{chunkId}/revectorize")
    public ApiResponse<Void> reVectorize(@PathVariable String chunkId) {
        KnowledgeChunk chunk = chunkService.getChunkByChunkId(chunkId);
        if (chunk == null) {
            return ApiResponse.error(404, "切片不存在");
        }
        chunkService.reVectorizeChunk(chunk);
        return ApiResponse.success();
    }

    @PostMapping("/rebuild/{kbId}")
    public ApiResponse<Void> rebuildKbVectors(@PathVariable Long kbId) {
        log.info("触发知识库向量重建: kbId={}", kbId);
        chunkService.rebuildKbVectors(kbId);
        return ApiResponse.success();
    }

    @GetMapping("/sync-status")
    public ApiResponse<Map<String, Object>> syncStatus(@RequestParam(required = false) Long kbId) {
        return ApiResponse.success(chunkService.getVectorSyncStatus(kbId));
    }
}