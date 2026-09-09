package com.ragstudy.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "rag")
public class RagConfig {

    private EmbeddingConfig embedding = new EmbeddingConfig();
    private ChunkerConfig chunker = new ChunkerConfig();
    private RetrievalConfig retrieval = new RetrievalConfig();
    private Bm25Config bm25 = new Bm25Config();
    private QdrantConfig qdrant = new QdrantConfig();

    public EmbeddingConfig getEmbedding() { return embedding; }
    public void setEmbedding(EmbeddingConfig embedding) { this.embedding = embedding; }
    public ChunkerConfig getChunker() { return chunker; }
    public void setChunker(ChunkerConfig chunker) { this.chunker = chunker; }
    public RetrievalConfig getRetrieval() { return retrieval; }
    public void setRetrieval(RetrievalConfig retrieval) { this.retrieval = retrieval; }
    public Bm25Config getBm25() { return bm25; }
    public void setBm25(Bm25Config bm25) { this.bm25 = bm25; }
    public QdrantConfig getQdrant() { return qdrant; }
    public void setQdrant(QdrantConfig qdrant) { this.qdrant = qdrant; }

    public static class EmbeddingConfig {
        private String modelPath = "classpath:models/onnx/model.onnx";
        private String tokenizerPath = "classpath:models/tokenizer.json";
        private int dimension = 512;
        private int batchSize = 32;

        public String getModelPath() { return modelPath; }
        public void setModelPath(String modelPath) { this.modelPath = modelPath; }
        public String getTokenizerPath() { return tokenizerPath; }
        public void setTokenizerPath(String tokenizerPath) { this.tokenizerPath = tokenizerPath; }
        public int getDimension() { return dimension; }
        public void setDimension(int dimension) { this.dimension = dimension; }
        public int getBatchSize() { return batchSize; }
        public void setBatchSize(int batchSize) { this.batchSize = batchSize; }
    }

    public static class ChunkerConfig {
        private int childSize = 300;
        private int parentSize = 1000;
        private int overlap = 50;

        public int getChildSize() { return childSize; }
        public void setChildSize(int childSize) { this.childSize = childSize; }
        public int getParentSize() { return parentSize; }
        public void setParentSize(int parentSize) { this.parentSize = parentSize; }
        public int getOverlap() { return overlap; }
        public void setOverlap(int overlap) { this.overlap = overlap; }
    }

    public static class RetrievalConfig {
        private int topK = 10;
        private double vectorWeight = 0.7;
        private double bm25Weight = 0.3;
        private double multiHopMinScore = 0.4;
        private int multiHopMinSources = 2;
        private int rerankTopK = 10;

        public int getTopK() { return topK; }
        public void setTopK(int topK) { this.topK = topK; }
        public double getVectorWeight() { return vectorWeight; }
        public void setVectorWeight(double vectorWeight) { this.vectorWeight = vectorWeight; }
        public double getBm25Weight() { return bm25Weight; }
        public void setBm25Weight(double bm25Weight) { this.bm25Weight = bm25Weight; }
        public double getMultiHopMinScore() { return multiHopMinScore; }
        public void setMultiHopMinScore(double multiHopMinScore) { this.multiHopMinScore = multiHopMinScore; }
        public int getMultiHopMinSources() { return multiHopMinSources; }
        public void setMultiHopMinSources(int multiHopMinSources) { this.multiHopMinSources = multiHopMinSources; }
        public int getRerankTopK() { return rerankTopK; }
        public void setRerankTopK(int rerankTopK) { this.rerankTopK = rerankTopK; }
    }

    public static class Bm25Config {
        private String indexPath = "./data/bm25_index";
        private boolean autoRebuild = true;

        public String getIndexPath() { return indexPath; }
        public void setIndexPath(String indexPath) { this.indexPath = indexPath; }
        public boolean isAutoRebuild() { return autoRebuild; }
        public void setAutoRebuild(boolean autoRebuild) { this.autoRebuild = autoRebuild; }
    }

    public static class QdrantConfig {
        private String host = "localhost";
        private int port = 6334;
        private String collectionName = "rag_knowledge";
        private String parentCollectionName = "rag_knowledge_parent";
        private int vectorSize = 512;

        public String getHost() { return host; }
        public void setHost(String host) { this.host = host; }
        public int getPort() { return port; }
        public void setPort(int port) { this.port = port; }
        public String getCollectionName() { return collectionName; }
        public void setCollectionName(String collectionName) { this.collectionName = collectionName; }
        public String getParentCollectionName() { return parentCollectionName; }
        public void setParentCollectionName(String parentCollectionName) { this.parentCollectionName = parentCollectionName; }
        public int getVectorSize() { return vectorSize; }
        public void setVectorSize(int vectorSize) { this.vectorSize = vectorSize; }
    }
}