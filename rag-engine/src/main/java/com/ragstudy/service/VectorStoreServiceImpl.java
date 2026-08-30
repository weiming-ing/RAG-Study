package com.ragstudy.service;

import com.ragstudy.config.RagConfig;
import com.ragstudy.model.vo.SearchResultVO;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Points;
import io.qdrant.client.grpc.Points.Filter;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.ScoredPoint;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.ExecutionException;

import static io.qdrant.client.PointIdFactory.id;
import static io.qdrant.client.QueryFactory.nearest;
import static io.qdrant.client.ValueFactory.value;
import static io.qdrant.client.VectorsFactory.vectors;
import static io.qdrant.client.ConditionFactory.matchKeyword;

/**
 * 向量存储服务实现（Qdrant）
 *
 * 核心职责：封装 Qdrant gRPC 客户端，提供向量存储和检索能力。
 *
 * 关键操作：
 *   - ensureCollection: 确保集合存在（自动创建，余弦距离）
 *   - upsert / upsertBatch: 写入/批量写入向量（含 payload 元数据）
 *   - search: 向量检索（最近邻查询，支持过滤条件）
 *   - deleteById: 删除指定向量
 *
 * 降级策略：Qdrant 不可用时 available=false，所有操作安全降级（返回空结果/跳过写入）
 */
@Service
public class VectorStoreServiceImpl implements VectorStoreService {

    private static final Logger log = LoggerFactory.getLogger(VectorStoreServiceImpl.class);

    private final RagConfig ragConfig;
    private QdrantClient client;
    private boolean available = false;

    public VectorStoreServiceImpl(RagConfig ragConfig) {
        this.ragConfig = ragConfig;
    }

    @PostConstruct
    public void init() {
        log.info("初始化向量数据库服务...");
        try {
            RagConfig.QdrantConfig qdrantConfig = ragConfig.getQdrant();
            client = new QdrantClient(
                    QdrantGrpcClient.newBuilder(qdrantConfig.getHost(), qdrantConfig.getPort(), false).build()
            );

            client.healthCheckAsync().get();
            available = true;
            log.info("Qdrant 连接成功: {}:{}", qdrantConfig.getHost(), qdrantConfig.getPort());
            log.info("向量数据库服务初始化完成");
        } catch (Exception e) {
            log.error("向量数据库连接失败: {}", e.getMessage());
            log.warn("Qdrant 服务不可用，将使用降级模式（仅 BM25 检索）");
            available = false;
        }
    }

    @Override
    public void upsert(String collectionName, String id, float[] vector, Map<String, Object> payload) {
        upsertBatch(collectionName, List.of(new VectorEntry(id, vector, payload)));
    }

    @Override
    public void upsertBatch(String collectionName, List<VectorEntry> entries) {
        // 降级处理：如果向量数据库不可用，直接返回
        if (!available) {
            log.warn("向量数据库服务不可用，跳过 {} 条向量入库", entries.size());
            return;
        }

        try {
            // 存储转换后的Qdrant点数据
            List<PointStruct> points = new ArrayList<>();

            // 遍历所有向量条目，转换为Qdrant PointStruct格式
            for (VectorEntry entry : entries) {
                // 构建Qdrant点：将字符串ID通过MD5转换为UUID，设置向量数据
                PointStruct.Builder builder = PointStruct.newBuilder()
                        .setId(id(UUID.nameUUIDFromBytes(entry.id().getBytes())))
                        .setVectors(vectors(entry.vector()));

                // 如果存在元数据payload，转换为Qdrant要求的格式并添加到点中
                if (entry.payload() != null && !entry.payload().isEmpty()) {
                    Map<String, io.qdrant.client.grpc.JsonWithInt.Value> grpcPayload = new HashMap<>();

                    // 遍历每个payload字段，根据数据类型转换为gRPC Value
                    for (Map.Entry<String, Object> kv : entry.payload().entrySet()) {
                        // 字符串类型转换
                        if (kv.getValue() instanceof String s) {
                            grpcPayload.put(kv.getKey(), value(s));
                        }
                        // 数字类型转换（统一转为long）
                        else if (kv.getValue() instanceof Number n) {
                            grpcPayload.put(kv.getKey(), value(n.longValue()));
                        }
                        // 布尔类型转换
                        else if (kv.getValue() instanceof Boolean b) {
                            grpcPayload.put(kv.getKey(), value(b));
                        }
                        // 不支持的类型会被忽略
                    }

                    // 将转换后的payload添加到点构建器
                    builder.putAllPayload(grpcPayload);
                }

                // 构建完成，添加到列表
                points.add(builder.build());
            }

            // 异步批量写入Qdrant，阻塞等待完成
            client.upsertAsync(collectionName, points).get();
            log.debug("批量向量入库成功: collection={}, count={}", collectionName, entries.size());
        } catch (Exception e) {
            // 捕获所有异常，记录错误日志，不抛出异常保证服务可用性
            log.error("向量入库失败: collection={}, count={}", collectionName, entries.size(), e);
        }
    }
    @Override
    public List<SearchResultVO> search(String collectionName, float[] queryVector,
                                        int topK, Map<String, String> filters) {
        if (!available) {
            log.warn("向量数据库服务不可用，返回空结果");
            return List.of();
        }

        try {
            Points.QueryPoints.Builder queryBuilder = Points.QueryPoints.newBuilder()
                    .setCollectionName(collectionName)
                    .setLimit(topK)
                    .setQuery(nearest(queryVector))
                    .setWithPayload(Points.WithPayloadSelector.newBuilder()
                            .setEnable(true).build());

            if (filters != null && !filters.isEmpty()) {
                Filter.Builder filterBuilder = Filter.newBuilder();
                for (Map.Entry<String, String> filter : filters.entrySet()) {
                    filterBuilder.addMust(matchKeyword(filter.getKey(), filter.getValue()));
                }
                queryBuilder.setFilter(filterBuilder.build());
            }

            List<ScoredPoint> scoredPoints = client.queryAsync(queryBuilder.build()).get();

            List<SearchResultVO> results = new ArrayList<>();
            for (ScoredPoint point : scoredPoints) {
                Map<String, Object> metadata = new HashMap<>();
                String content = null;
                Map<String, io.qdrant.client.grpc.JsonWithInt.Value> payloadMap = point.getPayloadMap();
                for (Map.Entry<String, io.qdrant.client.grpc.JsonWithInt.Value> entry : payloadMap.entrySet()) {
                    io.qdrant.client.grpc.JsonWithInt.Value v = entry.getValue();
                    if (v.hasStringValue()) {
                        String val = v.getStringValue();
                        if ("content".equals(entry.getKey())) {
                            content = val;
                        } else {
                            metadata.put(entry.getKey(), val);
                        }
                    } else if (v.hasIntegerValue()) {
                        metadata.put(entry.getKey(), v.getIntegerValue());
                    }
                }
                metadata.put("source", "vector");

                SearchResultVO result = SearchResultVO.builder()
                        .id(point.getId().getUuid())
                        .content(content)
                        .score(point.getScore())
                        .metadata(metadata)
                        .build();
                results.add(result);
            }

            log.debug("向量检索完成: collection={}, hits={}", collectionName, results.size());
            return results;
        } catch (Exception e) {
            log.error("向量检索失败: collection={}", collectionName, e);
            return List.of();
        }
    }

    @Override
    public void deleteById(String collectionName, String id) {
        if (!available) {
            return;
        }

        try {
            client.deleteAsync(collectionName,
                    List.of(id(UUID.nameUUIDFromBytes(id.getBytes()))),
                    null).get();
            log.debug("向量删除成功: collection={}, id={}", collectionName, id);
        } catch (Exception e) {
            log.error("向量删除失败: collection={}, id={}", collectionName, id, e);
        }
    }

    @Override
    public void ensureCollection(String collectionName, int vectorSize) {
        if (!available) {
            return;
        }

        try {
            boolean exists = client.collectionExistsAsync(collectionName).get();
            if (!exists) {
                client.createCollectionAsync(collectionName,
                        VectorParams.newBuilder()
                                .setSize(vectorSize)
                                .setDistance(Distance.Cosine)
                                .build(),
                        null).get();
                log.info("集合已创建: {} (dim={}, distance=Cosine)", collectionName, vectorSize);
            }
        } catch (Exception e) {
            log.error("确保集合存在失败: {}", collectionName, e);
        }
    }

    @PreDestroy
    public void destroy() {
        if (client != null) {
            try {
                client.close();
                log.info("Qdrant 客户端已关闭");
            } catch (Exception e) {
                log.error("Qdrant 客户端关闭失败", e);
            }
        }
    }
}