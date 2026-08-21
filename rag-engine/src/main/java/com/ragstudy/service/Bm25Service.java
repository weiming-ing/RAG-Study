package com.ragstudy.service;

import com.ragstudy.model.vo.SearchResultVO;

import java.util.List;

public interface Bm25Service {

    void indexDocument(String chunkId, String content);

    void indexDocuments(List<IndexEntry> entries);

    List<SearchResultVO> search(String query, int topK);

    void removeDocument(String chunkId);

    void rebuild();

    void clear();

    record IndexEntry(String chunkId, String content, String parentContent, String docName, String department) {}
}