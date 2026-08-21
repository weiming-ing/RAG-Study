package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.DocumentManualRequest;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.vo.DocumentVO;
import com.ragstudy.model.vo.ParseTaskVO;
import com.ragstudy.service.KnowledgeBaseService;
import com.ragstudy.service.ParseTaskService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/knowledge/{kbId}/documents")
public class DocumentController {

    private static final Logger log = LoggerFactory.getLogger(DocumentController.class);

    private final KnowledgeBaseService knowledgeBaseService;
    private final ParseTaskService parseTaskService;

    public DocumentController(KnowledgeBaseService knowledgeBaseService, ParseTaskService parseTaskService) {
        this.knowledgeBaseService = knowledgeBaseService;
        this.parseTaskService = parseTaskService;
    }

    @GetMapping
    public ApiResponse<IPage<DocumentVO>> list(
            @PathVariable Long kbId,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String fileType) {
        return ApiResponse.success(knowledgeBaseService.listDocuments(kbId, pageNum, pageSize, keyword, status, fileType));
    }

    @PostMapping("/upload")
    public ApiResponse<DocumentVO> upload(
            @PathVariable Long kbId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "tags", required = false) String tags) {
        log.info("上传文档: kbId={}, fileName={}", kbId, file.getOriginalFilename());
        return ApiResponse.success(knowledgeBaseService.uploadDocumentToKb(kbId, file, tags));
    }

    @PostMapping("/batch")
    public ApiResponse<Integer> batchUpload(
            @PathVariable Long kbId,
            @RequestParam("files") List<MultipartFile> files) {
        log.info("批量上传: kbId={}, count={}", kbId, files.size());
        int count = knowledgeBaseService.batchUploadDocuments(kbId, files);
        return ApiResponse.success(count);
    }

    @PostMapping("/manual")
    public ApiResponse<DocumentVO> manualCreate(
            @PathVariable Long kbId,
            @RequestBody DocumentManualRequest request) {
        log.info("手动录入: kbId={}, title={}", kbId, request.getTitle());
        return ApiResponse.success(knowledgeBaseService.createManualDocument(kbId, request));
    }

    @GetMapping("/{docId}")
    public ApiResponse<DocumentVO> getById(@PathVariable Long kbId, @PathVariable String docId) {
        return ApiResponse.success(knowledgeBaseService.getDocumentById(docId));
    }

    @PutMapping("/{docId}")
    public ApiResponse<DocumentVO> update(
            @PathVariable Long kbId,
            @PathVariable String docId,
            @RequestBody Map<String, Object> body) {
        return ApiResponse.success(knowledgeBaseService.updateDocument(docId, body));
    }

    @DeleteMapping("/{docId}")
    public ApiResponse<Void> delete(@PathVariable Long kbId, @PathVariable String docId) {
        knowledgeBaseService.deleteDocument(docId);
        return ApiResponse.success();
    }

    @PostMapping("/{docId}/reparse")
    public ApiResponse<Void> reparse(@PathVariable Long kbId, @PathVariable String docId) {
        knowledgeBaseService.reparseDocument(docId);
        return ApiResponse.success();
    }

    @PostMapping("/{docId}/restore")
    public ApiResponse<Void> restore(@PathVariable Long kbId, @PathVariable String docId) {
        knowledgeBaseService.restoreDocument(docId);
        return ApiResponse.success();
    }

    @DeleteMapping("/{docId}/purge")
    public ApiResponse<Void> purge(@PathVariable Long kbId, @PathVariable String docId) {
        knowledgeBaseService.purgeDocument(docId);
        return ApiResponse.success();
    }

    @GetMapping("/{docId}/tasks")
    public ApiResponse<List<ParseTaskVO>> getTasks(@PathVariable Long kbId, @PathVariable String docId) {
        return ApiResponse.success(parseTaskService.getTasksByDocumentId(docId));
    }

    @GetMapping("/{docId}/chunks")
    public ApiResponse<List<KnowledgeChunk>> getChunks(@PathVariable Long kbId, @PathVariable String docId) {
        return ApiResponse.success(knowledgeBaseService.getChunksByDocumentId(docId));
    }
}