package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.vo.SearchResultVO;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.cn.smart.SmartChineseAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.document.StoredField;
import org.apache.lucene.document.TextField;
import org.apache.lucene.index.*;
import org.apache.lucene.queryparser.classic.MultiFieldQueryParser;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.*;
import org.apache.lucene.store.FSDirectory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * BM25 全文索引服务实现（Apache Lucene）
 *
 * 核心职责：基于 Lucene 实现 BM25 关键词检索，作为向量检索的互补。
 *
 * 关键技术：
 *   - 分词器：SmartChineseAnalyzer（中文智能分词）
 *   - 并发控制：ReadWriteLock（写锁保护索引写入，读锁允许并发检索）
 *   - 索引字段：chunkId（主键）、content（索引+存储）、parentContent/docName/department（仅存储）
 *   - 分数归一化：score / maxScore 映射到 [0, 1] 区间
 *
 * 存储位置：本地文件系统（bm25_index/），通过 RagConfig 配置索引路径
 */
@Service
public class Bm25ServiceImpl implements Bm25Service {

    private static final Logger log = LoggerFactory.getLogger(Bm25ServiceImpl.class);

    private final RagConfig ragConfig;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    private volatile IndexWriter indexWriter;
    private volatile IndexReader indexReader;
    private volatile IndexSearcher indexSearcher;
    private volatile Analyzer analyzer;

    public Bm25ServiceImpl(RagConfig ragConfig) {
        this.ragConfig = ragConfig;
    }

    @PostConstruct
    public void init() {
        log.info("初始化 BM25 索引服务...");
        try {
            analyzer = new SmartChineseAnalyzer();
            IndexWriterConfig config = new IndexWriterConfig(analyzer);
            config.setOpenMode(IndexWriterConfig.OpenMode.CREATE_OR_APPEND);
            Path indexPath = Path.of(ragConfig.getBm25().getIndexPath());
            indexWriter = new IndexWriter(FSDirectory.open(indexPath), config);
            refreshReader();
            log.info("BM25 索引服务初始化完成, 索引路径: {}", indexPath.toAbsolutePath());
        } catch (IOException e) {
            log.error("BM25 索引初始化失败", e);
            throw new RuntimeException("BM25 索引初始化失败", e);
        }
    }

    private void refreshReader() throws IOException {
        if (indexReader != null) {
            indexReader.close();
        }
        indexReader = DirectoryReader.open(indexWriter);
        indexSearcher = new IndexSearcher(indexReader);
    }

    @Override
    public void indexDocument(String chunkId, String content) {
        indexDocuments(List.of(new IndexEntry(chunkId, content, "", "", "")));
    }

    @Override
    public void indexDocuments(List<IndexEntry> entries) {
        lock.writeLock().lock();
        try {
            List<Document> docs = new ArrayList<>();
            for (IndexEntry entry : entries) {
                Document doc = new Document();
                doc.add(new TextField("chunkId", entry.chunkId(), Field.Store.YES));
                doc.add(new TextField("content", entry.content(), Field.Store.NO));
                doc.add(new StoredField("content_stored", nullToEmpty(entry.content())));
                doc.add(new StoredField("parentContent", nullToEmpty(entry.parentContent())));
                doc.add(new StoredField("docName", nullToEmpty(entry.docName())));
                doc.add(new StoredField("department", nullToEmpty(entry.department())));
                docs.add(doc);
            }
            indexWriter.addDocuments(docs);
            indexWriter.commit();
            refreshReader();
            log.info("BM25 索引写入完成, 新增 {} 条记录", entries.size());
        } catch (IOException e) {
            log.error("BM25 索引写入失败", e);
            throw new RuntimeException("BM25 索引写入失败", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * BM25 检索：使用 SmartChineseAnalyzer 中文分词，MultiFieldQueryParser 多字段查询
     * 返回结果分数归一化到 [0, 1] 区间
     */
    @Override
    public List<SearchResultVO> search(String query, int topK) {
        lock.readLock().lock();
        try {
            QueryParser parser = new MultiFieldQueryParser(
                    new String[]{"content"},
                    analyzer
            );
            Query luceneQuery = parser.parse(QueryParser.escape(query));
            TopDocs topDocs = indexSearcher.search(luceneQuery, topK);

            List<SearchResultVO> results = new ArrayList<>();
            for (ScoreDoc scoreDoc : topDocs.scoreDocs) {
                Document doc = indexSearcher.storedFields().document(scoreDoc.doc);
                float maxScore = topDocs.scoreDocs.length > 0 ? topDocs.scoreDocs[0].score : 1.0f;
                SearchResultVO result = SearchResultVO.builder()
                        .id(doc.get("chunkId"))
                        .content(doc.get("content_stored"))
                        .parentContent(doc.get("parentContent"))
                        .score(normalizeScore(scoreDoc.score, maxScore))
                        .metadata(Map.of(
                                "docName", doc.get("docName"),
                                "department", doc.get("department"),
                                "source", "bm25"
                        ))
                        .build();
                results.add(result);
            }
            return results;
        } catch (Exception e) {
            log.error("BM25 检索失败: {}", e.getMessage());
            return List.of();
        } finally {
            lock.readLock().unlock();
        }
    }

    private double normalizeScore(float score, float maxScore) {
        if (maxScore <= 0) {
            return 0.0;
        }
        return score / maxScore;
    }

    @Override
    public void removeDocument(String chunkId) {
        lock.writeLock().lock();
        try {
            indexWriter.deleteDocuments(new TermQuery(new Term("chunkId", chunkId)));
            indexWriter.commit();
            refreshReader();
        } catch (IOException e) {
            log.error("BM25 删除文档失败: {}", chunkId, e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    @Override
    public void rebuild() {
        lock.writeLock().lock();
        try {
            indexWriter.deleteAll();
            indexWriter.commit();
            refreshReader();
            log.info("BM25 索引已清空，等待重建");
        } catch (IOException e) {
            log.error("BM25 索引重建失败", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    @Override
    public void clear() {
        rebuild();
    }

    private static String nullToEmpty(String value) {
        return value != null ? value : "";
    }

    @PreDestroy
    public void destroy() {
        try {
            if (indexReader != null) indexReader.close();
            if (indexWriter != null) indexWriter.close();
            if (analyzer != null) analyzer.close();
            log.info("BM25 索引服务已关闭");
        } catch (IOException e) {
            log.error("BM25 索引服务关闭失败", e);
        }
    }
}