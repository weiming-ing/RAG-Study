package com.ragstudy.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.ragstudy.common.ApiResponse;
import com.ragstudy.model.dto.KbAccessRequest;
import com.ragstudy.model.dto.KbConfigRequest;
import com.ragstudy.model.dto.KbCreateRequest;
import com.ragstudy.model.vo.KbAccessUserVO;
import com.ragstudy.model.vo.KbKnowledgeBaseVO;
import com.ragstudy.service.KnowledgeBaseManageService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/internal/knowledge-bases")
public class KnowledgeBaseController {

    private final KnowledgeBaseManageService kbManageService;

    public KnowledgeBaseController(KnowledgeBaseManageService kbManageService) {
        this.kbManageService = kbManageService;
    }

    @GetMapping
    public ApiResponse<IPage<KbKnowledgeBaseVO>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String category) {
        return ApiResponse.success(kbManageService.listKbs(pageNum, pageSize, keyword, category));
    }

    @GetMapping("/{id}")
    public ApiResponse<KbKnowledgeBaseVO> getById(@PathVariable Long id) {
        return ApiResponse.success(kbManageService.getKbById(id));
    }

    @PostMapping
    public ApiResponse<KbKnowledgeBaseVO> create(@RequestBody KbCreateRequest request) {
        return ApiResponse.success(kbManageService.createKb(request));
    }

    @PutMapping("/{id}")
    public ApiResponse<KbKnowledgeBaseVO> update(@PathVariable Long id, @RequestBody KbCreateRequest request) {
        return ApiResponse.success(kbManageService.updateKb(id, request));
    }

    @PutMapping("/{id}/config")
    public ApiResponse<Void> updateConfig(@PathVariable Long id, @RequestBody KbConfigRequest request) {
        kbManageService.updateKbConfig(id, request);
        return ApiResponse.success();
    }

    @PutMapping("/{id}/status")
    public ApiResponse<Void> updateStatus(@PathVariable Long id, @RequestParam String status) {
        kbManageService.updateStatus(id, status);
        return ApiResponse.success();
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        kbManageService.deleteKb(id);
        return ApiResponse.success();
    }

    @GetMapping("/{id}/users")
    public ApiResponse<List<KbAccessUserVO>> getAuthorizedUsers(@PathVariable Long id) {
        return ApiResponse.success(kbManageService.getAuthorizedUsers(id));
    }

    @PostMapping("/{id}/users")
    public ApiResponse<Void> grantAccess(@PathVariable Long id, @RequestBody KbAccessRequest request) {
        kbManageService.grantAccess(id, request);
        return ApiResponse.success();
    }

    @DeleteMapping("/{id}/users/{userId}")
    public ApiResponse<Void> revokeAccess(@PathVariable Long id, @PathVariable Long userId) {
        kbManageService.revokeAccess(id, userId);
        return ApiResponse.success();
    }
}