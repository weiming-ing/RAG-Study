package com.ragstudy.service;

import com.ragstudy.model.vo.SearchResultVO;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public interface VectorStoreService {

    void upsert(String collectionName, String id, float[] vector, Map<String, Object> payload);

    void upsertBatch(String collectionName, List<VectorEntry> entries);

    List<SearchResultVO> search(String collectionName, float[] queryVector, int topK, Map<String, String> filters);

    void deleteById(String collectionName, String id);

    void ensureCollection(String collectionName, int vectorSize);

    record VectorEntry(String id, float[] vector, Map<String, Object> payload) {}
}