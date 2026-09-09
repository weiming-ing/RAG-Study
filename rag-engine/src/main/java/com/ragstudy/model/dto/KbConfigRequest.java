package com.ragstudy.model.dto;

public class KbConfigRequest {

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
}