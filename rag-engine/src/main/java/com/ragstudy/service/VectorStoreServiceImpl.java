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

    /**
     * Spring 启动后自动初始化 Qdrant 连接
     *
     * 流程：
     *   1. 从配置中读取 Qdrant 地址（host:port）
     *   2. 构建 gRPC 客户端连接（非 TLS 模式）
     *   3. 执行健康检查确认连通性
     *   4. 成功 → available=true；失败 → available=false，系统降级为仅 BM25 检索
     *
     * 注意：gRPC 协议使用 HTTP/2 二进制传输，比 REST JSON 更高效
     */
    @PostConstruct
    public void init() {
        log.info("初始化向量数据库服务...");
        try {
            RagConfig.QdrantConfig qdrantConfig = ragConfig.getQdrant();
            // 构建 Qdrant gRPC 客户端（第三个参数 false=不使用 TLS 加密）
            client = new QdrantClient(
                    QdrantGrpcClient.newBuilder(qdrantConfig.getHost(), qdrantConfig.getPort(), false).build()
            );

            // 健康检查（阻塞等待结果），确保连接真实可用
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

    /**
     * 单条向量写入（委托给批量写入）
     * 将单条数据包装为单元素列表，复用 upsertBatch 的完整逻辑
     */
    @Override
    public void upsert(String collectionName, String id, float[] vector, Map<String, Object> payload) {
        upsertBatch(collectionName, List.of(new VectorEntry(id, vector, payload)));
    }

    /**
     * 批量向量写入 Qdrant
     *
     * 流程：
     *   1. 降级检查：如果 Qdrant 不可用，直接跳过
     *   2. 遍历每个条目，将字符串 ID 通过 MD5 转为确定性 UUID（保证幂等性）
     *   3. 将 payload 中的 Java 类型（String/Number/Boolean）转为 Qdrant gRPC Value 类型
     *   4. 异步批量写入（阻塞等待结果）
     *
     * 幂等性设计：同一个 chunkId 始终生成同一个 UUID，重复写入不会产生重复数据
     * 降级策略：Qdrant 不可用时静默跳过，不抛出异常
     */
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
                // 使用 UUID.nameUUIDFromBytes() 确定性生成，相同 chunkId 始终得到相同 UUID
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
                        // 不支持的类型（如 List、Map）会被忽略，Qdrant 不支持复杂嵌套类型
                    }

                    // 将转换后的payload添加到点构建器
                    builder.putAllPayload(grpcPayload);
                }

                // 构建完成，添加到列表
                points.add(builder.build());
            }

            // 异步批量写入Qdrant，阻塞等待完成
            // 使用 .get() 阻塞等待，确保写入完成后才继续后续流程
            client.upsertAsync(collectionName, points).get();
            log.debug("批量向量入库成功: collection={}, count={}", collectionName, entries.size());
        } catch (Exception e) {
            // 捕获所有异常，记录错误日志，不抛出异常保证服务可用性
            log.error("向量入库失败: collection={}, count={}", collectionName, entries.size(), e);
        }
    }
    /**
     * 向量检索（最近邻查询）
     *
     * 流程：
     *   1. 降级检查：Qdrant 不可用时直接返回空列表
     *   2. 构建查询请求：指定集合名、查询向量、返回数量、是否返回 payload
     *   3. 可选过滤：按 filters 条件（如按 documentId 过滤）限制检索范围
     *   4. 异步查询（阻塞等待），Qdrant 使用 HNSW 近似最近邻算法，O(log N) 复杂度
     *   5. 遍历结果：从 payload 中提取 content（文本）和 metadata（元数据），标记来源为 vector
     *   6. 构建 SearchResultVO 返回
     *
     * 关键设计：
     *   - payload 中存了 content 文本，检索命中后直接返回，无需回查 MySQL
     *   - 降级策略：检索失败时返回空列表，不抛出异常
     */
    @Override
    public List<SearchResultVO> search(String collectionName, float[] queryVector,
                                        int topK, Map<String, String> filters) {
        if (!available) {
            log.warn("向量数据库服务不可用，返回空结果");
            return List.of();
        }

        try {
            // 构建 Qdrant 查询请求
            Points.QueryPoints.Builder queryBuilder = Points.QueryPoints.newBuilder()
                    .setCollectionName(collectionName)             // 目标集合（如 rag_knowledge）
                    .setLimit(topK)                               // 返回 Top-K 条结果
                    .setQuery(nearest(queryVector))               // 使用余弦距离找最近邻
                    .setWithPayload(Points.WithPayloadSelector.newBuilder()
                            .setEnable(true).build());            // 返回 payload 元数据

            // 如果提供了过滤条件（如按知识库/文档筛选），则添加到查询中
            if (filters != null && !filters.isEmpty()) {
                Filter.Builder filterBuilder = Filter.newBuilder();
                for (Map.Entry<String, String> filter : filters.entrySet()) {
                    // matchKeyword 生成精确匹配条件，只有 payload 中对应字段完全匹配时才返回
                    filterBuilder.addMust(matchKeyword(filter.getKey(), filter.getValue()));
                }
                queryBuilder.setFilter(filterBuilder.build());
            }

            // 异步查询 Qdrant，阻塞等待结果
            List<ScoredPoint> scoredPoints = client.queryAsync(queryBuilder.build()).get();

            // 遍历结果，将 Qdrant ScoredPoint 转为项目的 SearchResultVO
            List<SearchResultVO> results = new ArrayList<>();
            for (ScoredPoint point : scoredPoints) {
                Map<String, Object> metadata = new HashMap<>();
                String content = null;
                // 从 payload 中提取数据：content 单独取出，其他字段放入 metadata
                Map<String, io.qdrant.client.grpc.JsonWithInt.Value> payloadMap = point.getPayloadMap();
                for (Map.Entry<String, io.qdrant.client.grpc.JsonWithInt.Value> entry : payloadMap.entrySet()) {
                    io.qdrant.client.grpc.JsonWithInt.Value v = entry.getValue();
                    if (v.hasStringValue()) {
                        String val = v.getStringValue();
                        if ("content".equals(entry.getKey())) {
                            content = val;  // content 单独存，用于后续构建 prompt
                        } else {
                            metadata.put(entry.getKey(), val);  // 其他字段（如 chunkId, docName）存入 metadata
                        }
                    } else if (v.hasIntegerValue()) {
                        metadata.put(entry.getKey(), v.getIntegerValue());
                    }
                }
                metadata.put("source", "vector");  // 标记来源为向量检索，方便后续混合检索区分

                // 构建统一的结果对象
                SearchResultVO result = SearchResultVO.builder()
                        .id(point.getId().getUuid())  // Qdrant 中的 UUID
                        .content(content)             // 切片文本
                        .score(point.getScore())      // 余弦相似度分数
                        .metadata(metadata)           // 元数据（docName, chunkId, parentChunkId 等）
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

    /**
     * 按 ID 删除向量
     * 使用与写入时相同的 UUID 生成策略（确定性 UUID），确保能删除之前写入的向量
     * 降级策略：Qdrant 不可用时静默跳过
     */
    @Override
    public void deleteById(String collectionName, String id) {
        if (!available) {
            return;
        }

        try {
            // 如果集合不存在，说明没有数据，无需删除
            boolean exists = client.collectionExistsAsync(collectionName).get();
            if (!exists) {
                log.debug("集合不存在，跳过删除: collection={}, id={}", collectionName, id);
                return;
            }

            // 使用与写入时相同的 UUID 生成策略（确定性 UUID），确保能定位到之前写入的向量
            client.deleteAsync(collectionName,
                    List.of(id(UUID.nameUUIDFromBytes(id.getBytes()))),
                    null).get();
            log.debug("向量删除成功: collection={}, id={}", collectionName, id);
        } catch (Exception e) {
            log.error("向量删除失败: collection={}, id={}", collectionName, id, e);
        }
    }

    /**
     * 确保 Qdrant 集合存在（不存在则自动创建）
     *
     * 集合配置：
     *   - size: 向量维度（512，匹配 bge-small-zh 模型输出维度）
     *   - distance: Cosine 余弦距离（计算相似度）
     *
     * 幂等性：如果集合已存在，直接返回，不重复创建
     */
    @Override
    public void ensureCollection(String collectionName, int vectorSize) {
        if (!available) {
            return;
        }

        try {
            // 检查集合是否已存在（幂等检查）
            boolean exists = client.collectionExistsAsync(collectionName).get();
            if (!exists) {
                // 创建集合：指定向量维度和距离度量方式
                client.createCollectionAsync(collectionName,
                        VectorParams.newBuilder()
                                .setSize(vectorSize)          // 向量维度（512）
                                .setDistance(Distance.Cosine)  // 余弦距离
                                .build(),
                        null).get();
                log.info("集合已创建: {} (dim={}, distance=Cosine)", collectionName, vectorSize);
            }
        } catch (Exception e) {
            log.error("确保集合存在失败: {}", collectionName, e);
        }
    }

    /**
     * Spring 容器关闭时释放 Qdrant gRPC 连接资源
     * 确保应用退出时不会遗留未关闭的 HTTP/2 连接
     */
    @PreDestroy
    public void destroy() {
        if (client != null) {
            try {
                // 关闭 gRPC 客户端，释放 HTTP/2 连接和线程池
                client.close();
                log.info("Qdrant 客户端已关闭");
            } catch (Exception e) {
                log.error("Qdrant 客户端关闭失败", e);
            }
        }
    }
}