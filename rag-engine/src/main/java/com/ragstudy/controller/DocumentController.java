package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.DocumentManualRequest;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.vo.DocumentVO;
import com.ragstudy.model.vo.ParseTaskVO;
import com.ragstudy.security.SecurityUtils;
import com.ragstudy.service.KnowledgeBaseManageService;
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
    private final KnowledgeBaseManageService kbManageService;

    public DocumentController(KnowledgeBaseService knowledgeBaseService, ParseTaskService parseTaskService,
                              KnowledgeBaseManageService kbManageService) {
        this.knowledgeBaseService = knowledgeBaseService;
        this.parseTaskService = parseTaskService;
        this.kbManageService = kbManageService;
    }

    /** KB 级访问隔离：读操作要求可读，写操作要求可写（visibility + kb_user_access + ROLE_ADMIN/owner） */
    private void checkReadable(Long kbId) {
        kbManageService.assertKbReadable(kbId, SecurityUtils.getCurrentUserId());
    }

    private void checkWritable(Long kbId) {
        kbManageService.assertKbWritable(kbId, SecurityUtils.getCurrentUserId());
    }

    @GetMapping
    public ApiResponse<IPage<DocumentVO>> list(
            @PathVariable Long kbId,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String fileType) {
        checkReadable(kbId);
        return ApiResponse.success(knowledgeBaseService.listDocuments(kbId, pageNum, pageSize, keyword, status, fileType));
    }

    @PostMapping("/upload")
    public ApiResponse<DocumentVO> upload(
            @PathVariable Long kbId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "tags", required = false) String tags,
            @RequestParam(value = "parsedContent", required = false) String parsedContent) {
        checkWritable(kbId);
        log.info("上传文档: kbId={}, fileName={}, parsedContent={} chars", kbId, file.getOriginalFilename(),
                parsedContent != null ? parsedContent.length() : 0);
        return ApiResponse.success(knowledgeBaseService.uploadDocumentToKb(kbId, file, tags, parsedContent));
    }

    @PostMapping("/batch")
    public ApiResponse<Integer> batchUpload(
            @PathVariable Long kbId,
            @RequestParam("files") List<MultipartFile> files) {
        checkWritable(kbId);
        log.info("批量上传: kbId={}, count={}", kbId, files.size());
        int count = knowledgeBaseService.batchUploadDocuments(kbId, files);
        return ApiResponse.success(count);
    }

    @PostMapping("/manual")
    public ApiResponse<DocumentVO> manualCreate(
            @PathVariable Long kbId,
            @RequestBody DocumentManualRequest request) {
        checkWritable(kbId);
        log.info("手动录入: kbId={}, title={}", kbId, request.getTitle());
        return ApiResponse.success(knowledgeBaseService.createManualDocument(kbId, request));
    }

    @GetMapping("/{docId}")
    public ApiResponse<DocumentVO> getById(@PathVariable Long kbId, @PathVariable String docId) {
        checkReadable(kbId);
        return ApiResponse.success(knowledgeBaseService.getDocumentById(docId));
    }

    @PutMapping("/{docId}")
    public ApiResponse<DocumentVO> update(
            @PathVariable Long kbId,
            @PathVariable String docId,
            @RequestBody Map<String, Object> body) {
        checkWritable(kbId);
        return ApiResponse.success(knowledgeBaseService.updateDocument(docId, body));
    }

    @DeleteMapping("/{docId}")
    public ApiResponse<Void> delete(@PathVariable Long kbId, @PathVariable String docId) {
        checkWritable(kbId);
        knowledgeBaseService.deleteDocument(docId);
        return ApiResponse.success();
    }

    @PostMapping("/{docId}/reparse")
    public ApiResponse<Void> reparse(@PathVariable Long kbId, @PathVariable String docId) {
        checkWritable(kbId);
        knowledgeBaseService.reparseDocument(docId);
        return ApiResponse.success();
    }

    @PostMapping("/{docId}/restore")
    public ApiResponse<Void> restore(@PathVariable Long kbId, @PathVariable String docId) {
        checkWritable(kbId);
        knowledgeBaseService.restoreDocument(docId);
        return ApiResponse.success();
    }

    @DeleteMapping("/{docId}/purge")
    public ApiResponse<Void> purge(@PathVariable Long kbId, @PathVariable String docId) {
        checkWritable(kbId);
        knowledgeBaseService.purgeDocument(docId);
        return ApiResponse.success();
    }

    @GetMapping("/{docId}/tasks")
    public ApiResponse<List<ParseTaskVO>> getTasks(@PathVariable Long kbId, @PathVariable String docId) {
        checkReadable(kbId);
        return ApiResponse.success(parseTaskService.getTasksByDocumentId(docId));
    }

    @GetMapping("/{docId}/chunks")
    public ApiResponse<List<KnowledgeChunk>> getChunks(@PathVariable Long kbId, @PathVariable String docId) {
        checkReadable(kbId);
        return ApiResponse.success(knowledgeBaseService.getChunksByDocumentId(docId));
    }
}