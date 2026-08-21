package com.ragstudy.model.vo;

import java.util.Map;

public class SearchResultVO {

    private String id;
    private String chunkId;
    private String content;
    private String parentContent;
    private String parentChunkId;
    private double score;
    private Map<String, Object> metadata;

    public SearchResultVO() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getChunkId() { return chunkId; }
    public void setChunkId(String chunkId) { this.chunkId = chunkId; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public String getParentContent() { return parentContent; }
    public void setParentContent(String parentContent) { this.parentContent = parentContent; }
    public String getParentChunkId() { return parentChunkId; }
    public void setParentChunkId(String parentChunkId) { this.parentChunkId = parentChunkId; }
    public double getScore() { return score; }
    public void setScore(double score) { this.score = score; }
    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private String id;
        private String chunkId;
        private String content;
        private String parentContent;
        private String parentChunkId;
        private double score;
        private Map<String, Object> metadata;

        public Builder id(String id) { this.id = id; return this; }
        public Builder chunkId(String chunkId) { this.chunkId = chunkId; return this; }
        public Builder content(String content) { this.content = content; return this; }
        public Builder parentContent(String parentContent) { this.parentContent = parentContent; return this; }
        public Builder parentChunkId(String parentChunkId) { this.parentChunkId = parentChunkId; return this; }
        public Builder score(double score) { this.score = score; return this; }
        public Builder metadata(Map<String, Object> metadata) { this.metadata = metadata; return this; }

        public SearchResultVO build() {
            SearchResultVO vo = new SearchResultVO();
            vo.id = this.id;
            vo.chunkId = this.chunkId;
            vo.content = this.content;
            vo.parentContent = this.parentContent;
            vo.parentChunkId = this.parentChunkId;
            vo.score = this.score;
            vo.metadata = this.metadata;
            return vo;
        }
    }
}