package com.ragstudy.model.vo;

public class KnowledgeStatsVO {

    private int totalDocuments;
    private int totalChunks;
    private long totalSize;
    private int indexedDocuments;
    private int pendingDocuments;

    public KnowledgeStatsVO() {}

    public int getTotalDocuments() { return totalDocuments; }
    public void setTotalDocuments(int totalDocuments) { this.totalDocuments = totalDocuments; }
    public int getTotalChunks() { return totalChunks; }
    public void setTotalChunks(int totalChunks) { this.totalChunks = totalChunks; }
    public long getTotalSize() { return totalSize; }
    public void setTotalSize(long totalSize) { this.totalSize = totalSize; }
    public int getIndexedDocuments() { return indexedDocuments; }
    public void setIndexedDocuments(int indexedDocuments) { this.indexedDocuments = indexedDocuments; }
    public int getPendingDocuments() { return pendingDocuments; }
    public void setPendingDocuments(int pendingDocuments) { this.pendingDocuments = pendingDocuments; }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private int totalDocuments;
        private int totalChunks;
        private long totalSize;
        private int indexedDocuments;
        private int pendingDocuments;

        public Builder totalDocuments(int totalDocuments) { this.totalDocuments = totalDocuments; return this; }
        public Builder totalChunks(int totalChunks) { this.totalChunks = totalChunks; return this; }
        public Builder totalSize(long totalSize) { this.totalSize = totalSize; return this; }
        public Builder indexedDocuments(int indexedDocuments) { this.indexedDocuments = indexedDocuments; return this; }
        public Builder pendingDocuments(int pendingDocuments) { this.pendingDocuments = pendingDocuments; return this; }

        public KnowledgeStatsVO build() {
            KnowledgeStatsVO vo = new KnowledgeStatsVO();
            vo.totalDocuments = this.totalDocuments;
            vo.totalChunks = this.totalChunks;
            vo.totalSize = this.totalSize;
            vo.indexedDocuments = this.indexedDocuments;
            vo.pendingDocuments = this.pendingDocuments;
            return vo;
        }
    }
}