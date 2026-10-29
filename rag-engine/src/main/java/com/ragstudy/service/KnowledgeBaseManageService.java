package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.common.BusinessException;
import com.ragstudy.config.RagConfig;
import com.ragstudy.model.dto.KbAccessRequest;
import com.ragstudy.model.dto.KbConfigRequest;
import com.ragstudy.model.dto.KbCreateRequest;
import com.ragstudy.model.entity.KbKnowledgeBase;
import com.ragstudy.model.entity.KbUserAccess;
import com.ragstudy.model.entity.KnowledgeChunk;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.SysUser;
import com.ragstudy.model.vo.KbAccessUserVO;
import com.ragstudy.model.vo.KbKnowledgeBaseVO;
import com.ragstudy.model.vo.AccessibleKbsVO;
import com.ragstudy.repository.*;
import com.ragstudy.security.SecurityUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 知识库管理服务
 *
 * 核心职责：知识库的CRUD管理 + 权限控制（RBAC）。
 *
 * 主要功能：
 *   - listKbs: 分页查询知识库（权限过滤：仅公开/自己拥有/有权限访问）
 *   - createKb: 创建知识库 → 初始配置默认检索参数 → 创建所有者权限
 *   - updateKb / updateKbConfig: 更新知识库基本信息和检索配置
 *   - grantAccess / revokeAccess: 授权/撤销用户访问权限
 *   - getAuthorizedUsers: 获取已授权用户列表
 *
 * 权限模型：
 *   - PUBLIC: 所有人可访问
 *   - PRIVATE: 仅授权用户可访问
 *   - 权限级别: ADMIN / EDIT / READ
 */
@Service
public class KnowledgeBaseManageService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseManageService.class);

    /** KB 可见级别（kb_knowledge_base.visibility） */
    public static final String VIS_PUBLIC = "PUBLIC";
    public static final String VIS_EMPLOYEE = "EMPLOYEE";
    public static final String VIS_MANAGEMENT = "MANAGEMENT";
    private static final Set<String> VALID_VISIBILITIES = Set.of(VIS_PUBLIC, VIS_EMPLOYEE, VIS_MANAGEMENT);

    private final KbKnowledgeBaseMapper kbMapper;
    private final KbUserAccessMapper kbUserAccessMapper;
    private final SysUserMapper sysUserMapper;
    private final KnowledgeDocumentMapper documentMapper;
    private final KnowledgeChunkMapper chunkMapper;
    private final VectorStoreService vectorStoreService;
    private final Bm25Service bm25Service;
    private final RagConfig ragConfig;

    public KnowledgeBaseManageService(KbKnowledgeBaseMapper kbMapper,
                                      KbUserAccessMapper kbUserAccessMapper,
                                      SysUserMapper sysUserMapper,
                                      KnowledgeDocumentMapper documentMapper,
                                      KnowledgeChunkMapper chunkMapper,
                                      VectorStoreService vectorStoreService,
                                      Bm25Service bm25Service,
                                      RagConfig ragConfig) {
        this.kbMapper = kbMapper;
        this.kbUserAccessMapper = kbUserAccessMapper;
        this.sysUserMapper = sysUserMapper;
        this.documentMapper = documentMapper;
        this.chunkMapper = chunkMapper;
        this.vectorStoreService = vectorStoreService;
        this.bm25Service = bm25Service;
        this.ragConfig = ragConfig;
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
            List<Long> grantedKbIds = kbUserAccessMapper.selectKbIdsByUserId(userId);
            wrapper.and(w -> {
                w.in(KbKnowledgeBase::getVisibility, VIS_PUBLIC, VIS_EMPLOYEE)
                        .or().eq(KbKnowledgeBase::getOwnerId, userId);
                if (!grantedKbIds.isEmpty()) {
                    w.or().in(KbKnowledgeBase::getId, grantedKbIds);
                }
            });
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
        assertKbReadable(id, SecurityUtils.getCurrentUserId());
        KbKnowledgeBaseVO vo = toVO(kb);
        vo.setAuthorizedUsers(getAuthorizedUsers(id));

        Long userId = SecurityUtils.getCurrentUserId();
        if (userId != null) {
            String accessLevel = kbUserAccessMapper.selectAccessLevel(id, userId);
            vo.setAccessLevel(accessLevel);
        }
        return vo;
    }

    /**
     * 创建知识库：持久化知识库记录 → 设置默认检索配置 → 分配 OWNER 权限给创建者
     */
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
        applyVisibility(kb, request.getVisibility(), request.getIsPublic());
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
        applyVisibility(kb, request.getVisibility(), request.getIsPublic());
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
        applyVisibility(kb, request.getVisibility(), null);
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

        List<KnowledgeDocument> documents = documentMapper.selectList(
                new LambdaQueryWrapper<KnowledgeDocument>().eq(KnowledgeDocument::getKbId, id));
        for (KnowledgeDocument doc : documents) {
            List<KnowledgeChunk> chunks = chunkMapper.selectByDocumentId(doc.getId());
            for (KnowledgeChunk chunk : chunks) {
                vectorStoreService.deleteById(ragConfig.getQdrant().getCollectionName(), chunk.getChunkId());
                bm25Service.removeDocument(chunk.getChunkId());
            }
            Set<String> parentChunkIds = chunks.stream()
                    .map(KnowledgeChunk::getParentChunkId)
                    .filter(pid -> pid != null && !pid.isEmpty())
                    .collect(Collectors.toSet());
            for (String parentChunkId : parentChunkIds) {
                vectorStoreService.deleteById(ragConfig.getQdrant().getParentCollectionName(), parentChunkId);
            }
            chunkMapper.delete(new LambdaQueryWrapper<KnowledgeChunk>()
                    .eq(KnowledgeChunk::getDocumentId, doc.getId()));
        }

        documentMapper.delete(new LambdaQueryWrapper<KnowledgeDocument>().eq(KnowledgeDocument::getKbId, id));
        kbUserAccessMapper.delete(new LambdaQueryWrapper<KbUserAccess>().eq(KbUserAccess::getKbId, id));
        kbMapper.deleteById(id);

        log.info("知识库已彻底删除: id={}, name={}, documents={}", id, kb.getName(), documents.size());
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
        // 越权修复：此前任何登录用户可给任何 KB 授权
        assertCanManageAccess(kbId, SecurityUtils.getCurrentUserId());

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
        assertCanManageAccess(kbId, SecurityUtils.getCurrentUserId());
        kbUserAccessMapper.delete(
                new LambdaQueryWrapper<KbUserAccess>()
                        .eq(KbUserAccess::getKbId, kbId)
                        .eq(KbUserAccess::getUserId, userId)
        );
    }

    /**
     * 解析用户可访问的知识库集合（三级可见级别的服务端强制依据）。
     *
     * userId 为 null 表示访客：仅 PUBLIC 级。
     * ROLE_ADMIN：全部知识库。
     * 其他用户：PUBLIC + EMPLOYEE + kb_user_access 授权记录 + 自己创建的。
     */
    public AccessibleKbsVO getAccessibleKbs(Long userId) {
        AccessibleKbsVO vo = new AccessibleKbsVO();
        boolean isAdmin = userId != null && isAdmin(userId);
        vo.setIsAdmin(isAdmin);

        if (userId == null) {
            List<Long> publicIds = kbMapper.selectList(
                            new LambdaQueryWrapper<KbKnowledgeBase>()
                                    .select(KbKnowledgeBase::getId)
                                    .eq(KbKnowledgeBase::getVisibility, VIS_PUBLIC))
                    .stream().map(KbKnowledgeBase::getId).collect(Collectors.toList());
            vo.setKbIds(publicIds);
            return vo;
        }

        if (isAdmin) {
            vo.setKbIds(kbMapper.selectList(
                            new LambdaQueryWrapper<KbKnowledgeBase>().select(KbKnowledgeBase::getId))
                    .stream().map(KbKnowledgeBase::getId).collect(Collectors.toList()));
            return vo;
        }

        // LinkedHashSet 去重保序
        Set<Long> ids = new LinkedHashSet<>();
        kbMapper.selectList(new LambdaQueryWrapper<KbKnowledgeBase>()
                        .select(KbKnowledgeBase::getId)
                        .in(KbKnowledgeBase::getVisibility, VIS_PUBLIC, VIS_EMPLOYEE))
                .forEach(kb -> ids.add(kb.getId()));
        ids.addAll(kbUserAccessMapper.selectKbIdsByUserId(userId));
        kbMapper.selectList(new LambdaQueryWrapper<KbKnowledgeBase>()
                        .select(KbKnowledgeBase::getId)
                        .eq(KbKnowledgeBase::getOwnerId, userId))
                .forEach(kb -> ids.add(kb.getId()));
        vo.setKbIds(new ArrayList<>(ids));
        return vo;
    }

    /** 供访客使用的 PUBLIC 库 id 集合（不依赖请求身份） */
    public List<Long> getPublicKbIds() {
        return getAccessibleKbs(null).getKbIds();
    }

    /**
     * KB 可读性断言：不可读抛 BusinessException（403 语义）。
     * 规则与 getAccessibleKbs 一致：PUBLIC/EMPLOYEE 对登录用户开放；
     * MANAGEMENT 仅授权人/owner/ROLE_ADMIN；访客仅 PUBLIC。
     */
    public void assertKbReadable(Long kbId, Long userId) {
        if (kbId == null) {
            return;
        }
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb == null) {
            throw new BusinessException("知识库不存在");
        }
        String vis = kb.getVisibility() == null ? VIS_EMPLOYEE : kb.getVisibility();

        if (VIS_PUBLIC.equals(vis)) {
            return;
        }
        if (userId == null) {
            throw new BusinessException("无权访问该知识库");
        }
        if (isAdmin(userId)
                || userId.equals(kb.getOwnerId())
                || kbUserAccessMapper.selectAccessLevel(kbId, userId) != null) {
            return;
        }
        if (VIS_EMPLOYEE.equals(vis)) {
            return;
        }
        throw new BusinessException("无权访问该知识库");
    }

    /**
     * KB 可写性断言：在可读基础上要求 EDIT/ADMIN 级授权、owner 或 ROLE_ADMIN。
     * 员工级/公共级 KB 对普通员工是只读的，写入由 owner/管理员/被授权者进行。
     */
    public void assertKbWritable(Long kbId, Long userId) {
        assertKbReadable(kbId, userId);
        if (userId == null) {
            throw new BusinessException("未登录");
        }
        if (isAdmin(userId)) {
            return;
        }
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb != null && userId.equals(kb.getOwnerId())) {
            return;
        }
        String level = kbUserAccessMapper.selectAccessLevel(kbId, userId);
        if ("EDIT".equals(level) || "ADMIN".equals(level)) {
            return;
        }
        throw new BusinessException("无权修改该知识库");
    }

    /** 授权管理权断言：仅 ROLE_ADMIN / KB owner / 该 KB ADMIN 级授权人可授予权限 */
    private void assertCanManageAccess(Long kbId, Long userId) {
        if (userId == null) {
            throw new BusinessException("未登录");
        }
        if (isAdmin(userId)) {
            return;
        }
        KbKnowledgeBase kb = kbMapper.selectById(kbId);
        if (kb != null && userId.equals(kb.getOwnerId())) {
            return;
        }
        if ("ADMIN".equals(kbUserAccessMapper.selectAccessLevel(kbId, userId))) {
            return;
        }
        throw new BusinessException("仅知识库管理员可管理授权");
    }

    /** 写入 visibility 并保持 is_public 同步（PUBLIC=1 其余=0），兼容未迁移读取点 */
    private void applyVisibility(KbKnowledgeBase kb, String visibility, Integer isPublic) {
        if (visibility != null) {
            if (!VALID_VISIBILITIES.contains(visibility)) {
                throw new BusinessException("无效的可见级别: " + visibility + "（可选 PUBLIC/EMPLOYEE/MANAGEMENT）");
            }
            kb.setVisibility(visibility);
            kb.setIsPublic(VIS_PUBLIC.equals(visibility) ? 1 : 0);
        } else if (isPublic != null) {
            // 旧字段兼容：未显式给 visibility 时按 is_public 推导
            kb.setVisibility(isPublic == 1 ? VIS_PUBLIC : VIS_MANAGEMENT);
            kb.setIsPublic(isPublic);
        } else if (kb.getVisibility() == null) {
            kb.setVisibility(VIS_EMPLOYEE);
            if (kb.getIsPublic() == null) {
                kb.setIsPublic(0);
            }
        }
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
        vo.setVisibilityLevel(kb.getVisibility());
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