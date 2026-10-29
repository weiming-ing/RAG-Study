package com.ragstudy.service;

import com.ragstudy.model.vo.SearchResultVO;

import java.util.List;
import java.util.Map;

public interface Bm25Service {

    void indexDocument(String chunkId, String content);

    void indexDocuments(List<IndexEntry> entries);

    List<SearchResultVO> search(String query, int topK);

    List<SearchResultVO> search(String query, int topK, Map<String, String> filters);

    void removeDocument(String chunkId);

    void rebuild();

    void clear();

    record IndexEntry(String chunkId, String content, String parentContent,
                      String docName, String department, String kbName,
                      String kbId, String documentId) {
        public IndexEntry(String chunkId, String content, String parentContent,
                          String docName, String department, String kbName) {
            this(chunkId, content, parentContent, docName, department, kbName, null, null);
        }
    }
}