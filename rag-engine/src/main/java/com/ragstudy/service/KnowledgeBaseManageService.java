package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.BusinessException;
import com.ragstudy.model.dto.KbAccessRequest;
import com.ragstudy.model.dto.KbConfigRequest;
import com.ragstudy.model.dto.KbCreateRequest;
import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.entity.KbUserAccess;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.model.vo.KbAccessUserVO;
import com.ragstudy.model.vo.KbKnowledgeBaseVO;
import com.ragstudy.repository.*;
import com.ragstudy.security.SecurityUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class KnowledgeBaseManageService {

    private final KbKnowledgeBaseMapper kbMapper;
    private final KbUserAccessMapper kbUserAccessMapper;
    private final SysUserMapper sysUserMapper;
    private final KnowledgeDocumentMapper documentMapper;

    public KnowledgeBaseManageService(KbKnowledgeBaseMapper kbMapper,
                                      KbUserAccessMapper kbUserAccessMapper,
                                      SysUserMapper sysUserMapper,
                                      KnowledgeDocumentMapper documentMapper) {
        this.kbMapper = kbMapper;
        this.kbUserAccessMapper = kbUserAccessMapper;
        this.sysUserMapper = sysUserMapper;
        this.documentMapper = documentMapper;
    }

    public IPage<KbKnowledgeBaseVO> listKbs(int pageNum, int pageSize, String keyword, String category) {
        Long userId = SecurityUtils.getCurrentUserId();
        boolean isAdmin = isAdmin(userId);

        Page<KbKnowledgeBase> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<KbKnowledgeBase> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(KbKnowledgeBase::getName, keyword)
                    .or().like(KbKnowledgeBase::getDescription, keyword));
        }
        if (StringUtils.hasText(category)) {
            wrapper.eq(KbKnowledgeBase::getCategory, category);
        }
        if (!isAdmin) {
            wrapper.and(w -> w.eq(KbKnowledgeBase::getIsPublic, 1)
                    .or().eq(KbKnowledgeBase::getOwnerId, userId));
        }
        wrapper.orderByDesc(KbKnowledgeBase::getCreateTime);

        IPage<KbKnowledgeBase> kbPage = kbMapper.selectPage(page, wrapper);

        return kbPage.convert(kb -> {
            KbKnowledgeBaseVO vo = toVO(kb);
            if (userId != null) {
                String accessLevel = kbUserAccessMapper.selectAccessLevel(kb.getId(), userId);
                vo.setAccessLevel(accessLevel);
            }
            return vo;
        });
    }

    public KbKnowledgeBaseVO getKbById(Long id) {
        KbKnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        KbKnowledgeBaseVO vo = toVO(kb);
        vo.setAuthorizedUsers(getAuthorizedUsers(id));

        Long userId = SecurityUtils.getCurrentUserId();
        if (userId != null) {
            String accessLevel = kbUserAccessMapper.selectAccessLevel(id, userId);
            vo.setAccessLevel(accessLevel);
        }
        return vo;
    }

    @Transactional
    public KbKnowledgeBaseVO createKb(KbCreateRequest request) {
        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            throw new BusinessException("未登录");
        }

        KbKnowledgeBase kb = new KbKnowledgeBase();
        kb.setName(request.getName());
        kb.setDescription(request.getDescription());
        kb.setCategory(request.getCategory());
        kb.setTags(request.getTags());
        kb.setCoverUrl(request.getCoverUrl());
        kb.setOwnerId(userId);
        kb.setDepartment(request.getDepartment());
        kb.setIsPublic(request.getIsPublic() != null ? request.getIsPublic() : 1);
        kb.setStatus("ENABLED");

        kb.setChunkSize(300);
        kb.setChunkOverlap(50);
        kb.setEmbeddingModel("default");
        kb.setTopK(10);
        kb.setSimilarityThreshold(0.6);
        kb.setVectorWeight(0.7);
        kb.setBm25Weight(0.3);
        kb.setEnableRerank(1);
        kb.setFilterLowScore(0);

        kbMapper.insert(kb);

        KbUserAccess access = new KbUserAccess();
        access.setKbId(kb.getId());
        access.setUserId(userId);
        access.setAccessLevel("ADMIN");
        kbUserAccessMapper.insert(access);

        return getKbById(kb.getId());
    }

    @Transactional
    public KbKnowledgeBaseVO updateKb(Long id, KbCreateRequest request) {
        KbKnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        if (request.getName() != null) kb.setName(request.getName());
        if (request.getDescription() != null) kb.setDescription(request.getDescription());
        if (request.getCategory() != null) kb.setCategory(request.getCategory());
        if (request.getTags() != null) kb.setTags(request.getTags());
        if (request.getCoverUrl() != null) kb.setCoverUrl(request.getCoverUrl());
        if (request.getDepartment() != null) kb.setDepartment(request.getDepartment());
        if (request.getIsPublic() != null) kb.setIsPublic(request.getIsPublic());
        kbMapper.updateById(kb);

        return getKbById(id);
    }

    @Transactional
    public void updateKbConfig(Long id, KbConfigRequest request) {
        KbKnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        if (request.getChunkSize() != null) kb.setChunkSize(request.getChunkSize());
        if (request.getChunkOverlap() != null) kb.setChunkOverlap(request.getChunkOverlap());
        if (request.getEmbeddingModel() != null) kb.setEmbeddingModel(request.getEmbeddingModel());
        if (request.getTopK() != null) kb.setTopK(request.getTopK());
        if (request.getSimilarityThreshold() != null) kb.setSimilarityThreshold(request.getSimilarityThreshold());
        if (request.getVectorWeight() != null) kb.setVectorWeight(request.getVectorWeight());
        if (request.getBm25Weight() != null) kb.setBm25Weight(request.getBm25Weight());
        if (request.getEnableRerank() != null) kb.setEnableRerank(request.getEnableRerank());
        if (request.getFilterLowScore() != null) kb.setFilterLowScore(request.getFilterLowScore());
        if (request.getPromptTemplate() != null) kb.setPromptTemplate(request.getPromptTemplate());
        if (request.getBlacklistWords() != null) kb.setBlacklistWords(request.getBlacklistWords());
        if (request.getWhitelistWords() != null) kb.setWhitelistWords(request.getWhitelistWords());
        kbMapper.updateById(kb);
    }

    @Transactional
    public void updateStatus(Long id, String status) {
        KbKnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        kb.setStatus(status);
        kbMapper.updateById(kb);
    }

    @Transactional
    public void deleteKb(Long id) {
        KbKnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        kbMapper.deleteById(id);
        kbUserAccessMapper.delete(new LambdaQueryWrapper<KbUserAccess>().eq(KbUserAccess::getKbId, id));
    }

    public List<KbAccessUserVO> getAuthorizedUsers(Long kbId) {
        List<KbUserAccess> accesses = kbUserAccessMapper.selectList(
                new LambdaQueryWrapper<KbUserAccess>().eq(KbUserAccess::getKbId, kbId)
        );

        return accesses.stream().map(access -> {
            KbAccessUserVO vo = new KbAccessUserVO();
            vo.setUserId(access.getUserId());
            vo.setAccessLevel(access.getAccessLevel());
            vo.setCreateTime(access.getCreateTime());

            SysUser user = sysUserMapper.selectById(access.getUserId());
            if (user != null) {
                vo.setUsername(user.getUsername());
                vo.setDisplayName(user.getDisplayName());
            }
            return vo;
        }).collect(Collectors.toList());
    }

    @Transactional
    public void grantAccess(Long kbId, KbAccessRequest request) {
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }

        for (Long userId : request.getUserIds()) {
            String existingLevel = kbUserAccessMapper.selectAccessLevel(kbId, userId);
            if (existingLevel != null) {
                kbUserAccessMapper.update(null,
                        new LambdaUpdateWrapper<KbUserAccess>()
                                .eq(KbUserAccess::getKbId, kbId)
                                .eq(KbUserAccess::getUserId, userId)
                                .set(KbUserAccess::getAccessLevel, request.getAccessLevel()));
            } else {
                KbUserAccess access = new KbUserAccess();
                access.setKbId(kbId);
                access.setUserId(userId);
                access.setAccessLevel(request.getAccessLevel());
                kbUserAccessMapper.insert(access);
            }
        }
    }

    @Transactional
    public void revokeAccess(Long kbId, Long userId) {
        kbUserAccessMapper.delete(
                new LambdaQueryWrapper<KbUserAccess>()
                        .eq(KbUserAccess::getKbId, kbId)
                        .eq(KbUserAccess::getUserId, userId)
        );
    }

    private KbKnowledgeBaseVO toVO(KbKnowledgeBase kb) {
        KbKnowledgeBaseVO vo = new KbKnowledgeBaseVO();
        vo.setId(kb.getId());
        vo.setName(kb.getName());
        vo.setDescription(kb.getDescription());
        vo.setCategory(kb.getCategory());
        vo.setTags(kb.getTags());
        vo.setCoverUrl(kb.getCoverUrl());
        vo.setOwnerId(kb.getOwnerId());
        vo.setDepartment(kb.getDepartment());
        vo.setIsPublic(kb.getIsPublic());
        vo.setStatus(kb.getStatus());

        Long docCount = documentMapper.selectCount(
                new LambdaQueryWrapper<KnowledgeDocument>().eq(KnowledgeDocument::getKbId, kb.getId())
        );
        vo.setDocumentCount(docCount);

        vo.setChunkSize(kb.getChunkSize());
        vo.setChunkOverlap(kb.getChunkOverlap());
        vo.setEmbeddingModel(kb.getEmbeddingModel());
        vo.setTopK(kb.getTopK());
        vo.setSimilarityThreshold(kb.getSimilarityThreshold());
        vo.setVectorWeight(kb.getVectorWeight());
        vo.setBm25Weight(kb.getBm25Weight());
        vo.setEnableRerank(kb.getEnableRerank());
        vo.setFilterLowScore(kb.getFilterLowScore());
        vo.setPromptTemplate(kb.getPromptTemplate());
        vo.setBlacklistWords(kb.getBlacklistWords());
        vo.setWhitelistWords(kb.getWhitelistWords());
        vo.setCreateTime(kb.getCreateTime());
        vo.setUpdateTime(kb.getUpdateTime());

        if (kb.getOwnerId() != null) {
            SysUser owner = sysUserMapper.selectById(kb.getOwnerId());
            if (owner != null) {
                vo.setOwnerName(owner.getDisplayName());
            }
        }
        return vo;
    }

    private boolean isAdmin(Long userId) {
        if (userId == null) return false;
        List<String> roles = sysUserMapper.selectRoleCodesByUserId(userId);
        return roles != null && roles.contains("ROLE_ADMIN");
    }
}