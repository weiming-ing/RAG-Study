package com.ragstudy.model.vo;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;
import java.util.List;

public class KbKnowledgeBaseVO {

    private Long id;
    private String name;
    private String description;
    private String category;
    private String tags;
    private String coverUrl;
    private Long ownerId;
    private String ownerName;
    private String department;
    private Integer isPublic;
    private String status;

    @JsonProperty("docCount")
    private Long documentCount;

    private String accessLevel;

    private Integer chunkSize;
    private Integer chunkOverlap;
    private String embeddingModel;
    private Integer topK;
    private Double similarityThreshold;
    private Double vectorWeight;
    private Double bm25Weight;
    private Integer enableRerank;
    private Integer filterLowScore;
    private String promptTemplate;
    private String blacklistWords;
    private String whitelistWords;

    private List<KbAccessUserVO> authorizedUsers;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }
    public String getTags() { return tags; }
    public void setTags(String tags) { this.tags = tags; }
    public String getCoverUrl() { return coverUrl; }
    public void setCoverUrl(String coverUrl) { this.coverUrl = coverUrl; }
    public Long getOwnerId() { return ownerId; }
    public void setOwnerId(Long ownerId) { this.ownerId = ownerId; }
    public String getOwnerName() { return ownerName; }
    public void setOwnerName(String ownerName) { this.ownerName = ownerName; }
    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }
    public Integer getIsPublic() { return isPublic; }
    public void setIsPublic(Integer isPublic) { this.isPublic = isPublic; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getDocumentCount() { return documentCount; }
    public void setDocumentCount(Long documentCount) { this.documentCount = documentCount; }
    public String getAccessLevel() { return accessLevel; }
    public void setAccessLevel(String accessLevel) { this.accessLevel = accessLevel; }
    public Integer getChunkSize() { return chunkSize; }
    public void setChunkSize(Integer chunkSize) { this.chunkSize = chunkSize; }
    public Integer getChunkOverlap() { return chunkOverlap; }
    public void setChunkOverlap(Integer chunkOverlap) { this.chunkOverlap = chunkOverlap; }
    public String getEmbeddingModel() { return embeddingModel; }
    public void setEmbeddingModel(String embeddingModel) { this.embeddingModel = embeddingModel; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Double getSimilarityThreshold() { return similarityThreshold; }
    public void setSimilarityThreshold(Double similarityThreshold) { this.similarityThreshold = similarityThreshold; }
    public Double getVectorWeight() { return vectorWeight; }
    public void setVectorWeight(Double vectorWeight) { this.vectorWeight = vectorWeight; }
    public Double getBm25Weight() { return bm25Weight; }
    public void setBm25Weight(Double bm25Weight) { this.bm25Weight = bm25Weight; }
    public Integer getEnableRerank() { return enableRerank; }
    public void setEnableRerank(Integer enableRerank) { this.enableRerank = enableRerank; }
    public Integer getFilterLowScore() { return filterLowScore; }
    public void setFilterLowScore(Integer filterLowScore) { this.filterLowScore = filterLowScore; }
    public String getPromptTemplate() { return promptTemplate; }
    public void setPromptTemplate(String promptTemplate) { this.promptTemplate = promptTemplate; }
    public String getBlacklistWords() { return blacklistWords; }
    public void setBlacklistWords(String blacklistWords) { this.blacklistWords = blacklistWords; }
    public String getWhitelistWords() { return whitelistWords; }
    public void setWhitelistWords(String whitelistWords) { this.whitelistWords = whitelistWords; }
    public List<KbAccessUserVO> getAuthorizedUsers() { return authorizedUsers; }
    public void setAuthorizedUsers(List<KbAccessUserVO> authorizedUsers) { this.authorizedUsers = authorizedUsers; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}