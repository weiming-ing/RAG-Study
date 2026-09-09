package com.ragstudy.service;

import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import ai.onnxruntime.*;
import com.ragstudy.config.RagConfig;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.FloatBuffer;
import java.nio.LongBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.*;

/**
 * 文本向量化服务实现（ONNX Runtime 本地推理）
 *
 * 核心职责：将文本转换为 512 维语义向量，使用 bge-small-zh 模型。
 *
 * 技术栈：
 *   - 推理引擎：ONNX Runtime（本地 CPU 推理，无需 GPU）
 *   - 模型：bge-small-zh（512 维中文语义向量模型）
 *   - 分词器：HuggingFace Tokenizer（DJL 封装）
 *   - 池化策略：Mean Pooling（对 attention_mask 有效位置取平均）
 *   - 输出后处理：L2 归一化（使向量模长为 1）
 *
 * 降级策略：模型未初始化时使用随机归一化向量，保证系统不崩溃
 */
@Service
public class EmbeddingServiceImpl implements EmbeddingService {

    private static final Logger log = LoggerFactory.getLogger(EmbeddingServiceImpl.class);

    private final RagConfig ragConfig;
    private OrtEnvironment env;
    private OrtSession session;
    private HuggingFaceTokenizer tokenizer;
    private boolean initialized = false;
    private final List<Path> tempFiles = new ArrayList<>();

    /**
     * 构造函数，注入配置
     * @param ragConfig 全局配置，包含模型路径、维度等参数
     */
    public EmbeddingServiceImpl(RagConfig ragConfig) {
        this.ragConfig = ragConfig;
    }

    /**
     * 初始化服务（Spring 启动后自动执行）
     * 加载 ONNX 模型和分词器，设置推理优化选项
     * 如果加载失败，设置 initialized=false，后续使用降级方案
     */
    @PostConstruct
    public void init() {
        log.info("初始化 Embedding 服务...");
        try {
            RagConfig.EmbeddingConfig embeddingConfig = ragConfig.getEmbedding();
            String modelPath = resolvePath(embeddingConfig.getModelPath());
            String tokenizerPath = resolvePath(embeddingConfig.getTokenizerPath());

            log.info("加载 ONNX 模型: {}", modelPath);
            // 创建 ONNX Runtime 环境，全局单例
            env = OrtEnvironment.getEnvironment();
            // 创建会话选项，开启全量优化（图优化、常量折叠等）
            OrtSession.SessionOptions options = new OrtSession.SessionOptions();
            options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
            // 创建推理会话，加载模型文件
            session = env.createSession(modelPath, options);

            log.info("加载分词器: {}", tokenizerPath);
            // 加载 HuggingFace 分词器，由 DJL 封装
            tokenizer = HuggingFaceTokenizer.newInstance(Path.of(tokenizerPath));

            initialized = true;
            log.info("Embedding 服务初始化完成 - 模型: {}, 向量维度: {}",
                    modelPath, embeddingConfig.getDimension());
        } catch (Exception e) {
            log.error("Embedding 服务初始化失败: {}", e.getMessage(), e);
            initialized = false;
        }
    }

    /**
     * 解析路径，支持 classpath: 前缀。
     * 优先尝试文件系统路径；若资源在 JAR 内部，则复制到临时文件。
     * @param path 配置中的路径
     * @return 可用的文件系统绝对路径
     */
    private String resolvePath(String path) {
        if (path.startsWith("classpath:")) {
            String classpathPath = path.substring("classpath:".length());
            ClassPathResource resource = new ClassPathResource(classpathPath);
            try {
                // 优先尝试直接文件访问（IDE 开发环境）
                return resource.getFile().getAbsolutePath();
            } catch (IOException e) {
                // 资源在 JAR 内部，无法直接获取文件路径，复制到临时文件
                log.info("classpath 资源在 JAR 内，复制到临时文件: {}", classpathPath);
                try (InputStream is = resource.getInputStream()) {
                    String suffix = classpathPath.substring(classpathPath.lastIndexOf('.'));
                    Path tempFile = Files.createTempFile("rag-embedding-", suffix);
                    Files.copy(is, tempFile, StandardCopyOption.REPLACE_EXISTING);
                    tempFile.toFile().deleteOnExit();
                    tempFiles.add(tempFile);
                    return tempFile.toAbsolutePath().toString();
                } catch (IOException ex) {
                    throw new RuntimeException("无法从 JAR 中提取 classpath 资源: " + classpathPath, ex);
                }
            }
        }
        return path;
    }

    /**
     * 获取输出向量维度（从配置读取）
     * @return 向量维度，通常是 512
     */
    @Override
    public int getDimension() {
        return ragConfig.getEmbedding().getDimension();
    }

    /**
     * 单条文本向量化（对外接口）
     * @param text 输入文本
     * @return 归一化后的 512 维语义向量
     */
    @Override
    public float[] embed(String text) {
        if (!initialized) {
            // 降级方案：模型加载失败时返回随机归一化向量，保证系统不崩溃
            log.warn("Embedding 服务未初始化，使用随机向量作为降级方案");
            return generateFallbackVector();
        }

        try {
            // 实际推理逻辑在私有方法中
            return doEmbed(text);
        } catch (Exception e) {
            // 截断过长文本，方便日志查看
            log.error("向量化失败: text={}", text.substring(0, Math.min(50, text.length())), e);
            throw new RuntimeException("向量化失败: " + e.getMessage(), e);
        }
    }

    /**
     * 批量文本向量化（对外接口）
     * 将多个文本一次性推理，比多次单条推理快 10-20 倍
     * @param texts 多条文本组成的列表
     * @return 对应的归一化向量列表
     */
    @Override
    public List<float[]> embedBatch(List<String> texts) {
        if (!initialized) {
            log.warn("Embedding 服务未初始化，批量使用随机向量作为降级方案");
            return texts.stream().map(t -> generateFallbackVector()).collect(java.util.stream.Collectors.toList());
        }

        if (texts.isEmpty()) {
            return List.of();
        }

        try {
            return doEmbedBatch(texts);
        } catch (Exception e) {
            log.error("批量向量化失败: count={}, error={}", texts.size(), e.getMessage(), e);
            // 降级：返回零向量，保证流程继续
            List<float[]> fallback = new ArrayList<>();
            for (String text : texts) {
                fallback.add(new float[ragConfig.getEmbedding().getDimension()]);
            }
            return fallback;
        }
    }

    /**
     * ONNX 模型推理：tokenize → 构建输入张量 → 推理 → Mean Pooling → L2 归一化
     */
    private float[] doEmbed(String text) throws OrtException {
        ai.djl.huggingface.tokenizers.Encoding encoding = tokenizer.encode(text);
        long[] inputIds = encoding.getIds();
        long[] attentionMask = encoding.getAttentionMask();
        long[] tokenTypeIds = encoding.getTypeIds();

        int seqLength = inputIds.length;
        long[] shape = {1, seqLength};

        Map<String, OnnxTensor> inputs = new HashMap<>();
        inputs.put("input_ids", OnnxTensor.createTensor(env, LongBuffer.wrap(inputIds), shape));
        inputs.put("attention_mask", OnnxTensor.createTensor(env, LongBuffer.wrap(attentionMask), shape));
        inputs.put("token_type_ids", OnnxTensor.createTensor(env, LongBuffer.wrap(tokenTypeIds), shape));

        OrtSession.Result result = session.run(inputs);

        String outputName = session.getOutputNames().iterator().next();
        OnnxTensor outputTensor = (OnnxTensor) result.get(outputName).get();

        long[] outputShape = outputTensor.getInfo().getShape();
        if (outputShape.length == 3) {
            return meanPooling(outputTensor, seqLength, attentionMask);
        } else if (outputShape.length == 2) {
            return extractVector(outputTensor);
        } else {
            throw new RuntimeException("不支持的输出形状: " + Arrays.toString(outputShape));
        }
    }

    /**
     * 批量 ONNX 推理：将所有文本填充到相同长度，一次 session.run 完成批量推理
     */
    private List<float[]> doEmbedBatch(List<String> texts) throws OrtException {
        int batchSize = texts.size();
        int dimension = ragConfig.getEmbedding().getDimension();

        ai.djl.huggingface.tokenizers.Encoding[] encodings = new ai.djl.huggingface.tokenizers.Encoding[batchSize];
        int maxSeqLen = 0;
        for (int i = 0; i < batchSize; i++) {
            encodings[i] = tokenizer.encode(texts.get(i));
            maxSeqLen = Math.max(maxSeqLen, encodings[i].getIds().length);
        }

        long[] flatInputIds = new long[batchSize * maxSeqLen];
        long[] flatAttentionMask = new long[batchSize * maxSeqLen];
        long[] flatTokenTypeIds = new long[batchSize * maxSeqLen];

        long[][] attentionMasks = new long[batchSize][maxSeqLen];

        for (int i = 0; i < batchSize; i++) {
            ai.djl.huggingface.tokenizers.Encoding enc = encodings[i];
            long[] ids = enc.getIds();
            long[] mask = enc.getAttentionMask();
            long[] typeIds = enc.getTypeIds();

            int offset = i * maxSeqLen;
            for (int j = 0; j < ids.length; j++) {
                flatInputIds[offset + j] = ids[j];
                flatAttentionMask[offset + j] = mask[j];
                flatTokenTypeIds[offset + j] = typeIds[j];
                attentionMasks[i][j] = mask[j];
            }
        }

        long[] shape = {batchSize, maxSeqLen};

        Map<String, OnnxTensor> inputs = new HashMap<>();
        inputs.put("input_ids", OnnxTensor.createTensor(env, LongBuffer.wrap(flatInputIds), shape));
        inputs.put("attention_mask", OnnxTensor.createTensor(env, LongBuffer.wrap(flatAttentionMask), shape));
        inputs.put("token_type_ids", OnnxTensor.createTensor(env, LongBuffer.wrap(flatTokenTypeIds), shape));

        OrtSession.Result result = session.run(inputs);

        String outputName = session.getOutputNames().iterator().next();
        OnnxTensor outputTensor = (OnnxTensor) result.get(outputName).get();

        long[] outputShape = outputTensor.getInfo().getShape();
        if (outputShape.length == 3) {
            return batchMeanPooling(outputTensor, batchSize, maxSeqLen, attentionMasks);
        } else if (outputShape.length == 2) {
            return batchExtractVectors(outputTensor, batchSize, dimension);
        } else {
            throw new RuntimeException("不支持的输出形状: " + Arrays.toString(outputShape));
        }
    }

    /**
     * 批量 Mean Pooling：对每个样本的 attention_mask=1 位置取平均，然后 L2 归一化
     *
     * ONNX 模型输出形状为 [batch, seq_len, hidden_size] 三维张量，
     * 需要将每个 token 位置的向量合并为句子级向量。
     * 只对 attention_mask=1（有效 token）的位置取平均，忽略 padding 位置。
     *
     * @param outputTensor  ONNX 模型输出张量
     * @param batchSize     批次大小
     * @param maxSeqLen     最大序列长度（已填充对齐）
     * @param attentionMasks 每个样本的 attention_mask 矩阵
     * @return 归一化后的向量列表
     */
    private List<float[]> batchMeanPooling(OnnxTensor outputTensor, int batchSize, int maxSeqLen, long[][] attentionMasks) throws OrtException {
        long[] shape = outputTensor.getInfo().getShape();
        int hiddenSize = (int) shape[2];
        FloatBuffer buffer = outputTensor.getFloatBuffer();

        List<float[]> result = new ArrayList<>(batchSize);
        for (int b = 0; b < batchSize; b++) {
            // 遍历每个样本的每个维度，只累加 attention_mask=1 的有效位置
            float[] pooled = new float[hiddenSize];
            for (int j = 0; j < hiddenSize; j++) {
                float sum = 0f;
                int count = 0;
                for (int i = 0; i < maxSeqLen; i++) {
                    if (attentionMasks[b][i] == 1) {
                        // 计算 buffer 中的偏移量：b * maxSeqLen * hiddenSize + i * hiddenSize + j
                        sum += buffer.get(b * maxSeqLen * hiddenSize + i * hiddenSize + j);
                        count++;
                    }
                }
                pooled[j] = count > 0 ? sum / count : 0f;
            }
            // 池化后做 L2 归一化，使向量模长变为 1
            result.add(l2Normalize(pooled));
        }
        return result;
    }

    /**
     * 批量提取向量（2D 输出）：直接取每个样本的向量并 L2 归一化
     *
     * 某些 ONNX 模型输出已经是 [batch, hidden_size] 二维形状，
     * 不需要 Mean Pooling，直接按批次索引提取即可。
     *
     * @param outputTensor  ONNX 模型输出张量
     * @param batchSize     批次大小
     * @param dimension     向量维度
     * @return 归一化后的向量列表
     */
    private List<float[]> batchExtractVectors(OnnxTensor outputTensor, int batchSize, int dimension) throws OrtException {
        FloatBuffer buffer = outputTensor.getFloatBuffer();
        List<float[]> result = new ArrayList<>(batchSize);
        for (int b = 0; b < batchSize; b++) {
            float[] vector = new float[dimension];
            // 移动 buffer 指针到当前样本的起始位置
            buffer.position(b * dimension);
            // 从 buffer 中读取当前样本的向量
            buffer.get(vector);
            result.add(l2Normalize(vector));
        }
        return result;
    }

    /**
     * L2 归一化：使向量模长为 1
     *
     * 归一化后，余弦相似度 cos(v1, v2) = v1·v2 / (|v1|×|v2|) 简化为点积 v1·v2，
     * 大幅提升 Qdrant 向量检索的运算速度。
     *
     * 数学公式：v_i = v_i / sqrt(sum(v_j^2))
     *
     * @param vector 输入向量
     * @return 归一化后的向量（模长=1）
     */
    private float[] l2Normalize(float[] vector) {
        // 计算向量各分量的平方和（模长的平方）
        float norm = 0f;
        for (float v : vector) {
            norm += v * v;
        }
        // 计算模长
        norm = (float) Math.sqrt(norm);
        // 每个分量除以模长，使向量模长变为 1
        if (norm > 0) {
            for (int i = 0; i < vector.length; i++) {
                vector[i] /= norm;
            }
        }
        return vector;
    }

    /**
     * Mean Pooling：对 attention_mask=1 的位置取平均，生成句子级向量，然后 L2 归一化
     *
     * ONNX 模型输出形状为 [1, seq_len, hidden_size] 三维张量（单条推理），
     * 每个 token 位置对应一个 768 维向量，需要合并为一个句子级向量。
     * 只对 attention_mask=1 的有效 token 取平均，忽略 padding 位置。
     *
     * 处理流程：
     *   1. 遍历每个隐藏层维度 j
     *   2. 对每个维度，累加所有 attention_mask=1 的 token 的该维度值
     *   3. 除以有效 token 数，得到该维度的平均值
     *   4. L2 归一化
     *
     * @param outputTensor  ONNX 模型输出张量 [1, seq_len, hidden_size]
     * @param seqLength     序列长度
     * @param attentionMask attention_mask 数组（1=有效, 0=padding）
     * @return 归一化后的句子向量
     */
    private float[] meanPooling(OnnxTensor outputTensor, int seqLength, long[] attentionMask) throws OrtException {
        long[] shape = outputTensor.getInfo().getShape();
        int hiddenSize = (int) shape[2];
        FloatBuffer buffer = outputTensor.getFloatBuffer();

        // 对每个隐藏层维度，只累加 attention_mask=1 的有效 token 位置
        float[] pooled = new float[hiddenSize];
        for (int j = 0; j < hiddenSize; j++) {
            float sum = 0f;
            int count = 0;
            for (int i = 0; i < seqLength; i++) {
                if (attentionMask[i] == 1) {
                    // 计算 buffer 偏移量：i * hiddenSize + j
                    sum += buffer.get(i * hiddenSize + j);
                    count++;
                }
            }
            // 取平均，得到该维度的句子级表示
            pooled[j] = count > 0 ? sum / count : 0f;
        }

        // L2 归一化
        float norm = 0f;
        for (float v : pooled) {
            norm += v * v;
        }
        norm = (float) Math.sqrt(norm);
        if (norm > 0) {
            for (int i = 0; i < pooled.length; i++) {
                pooled[i] /= norm;
            }
        }

        return pooled;
    }

    /**
     * 提取向量（2D 输出）：直接取第一行作为句子向量
     *
     * 某些 ONNX 模型输出已经是 [1, hidden_size] 二维形状（如 CLS token 输出），
     * 不需要 Mean Pooling，直接提取整行向量并 L2 归一化。
     *
     * @param outputTensor ONNX 模型输出张量 [1, hidden_size]
     * @return 归一化后的向量
     */
    private float[] extractVector(OnnxTensor outputTensor) throws OrtException {
        long[] shape = outputTensor.getInfo().getShape();
        int dim = (int) shape[1];
        float[] vector = new float[dim];
        FloatBuffer buffer = outputTensor.getFloatBuffer();
        // 读取整行向量
        buffer.get(vector);

        // L2 归一化
        float norm = 0f;
        for (float v : vector) {
            norm += v * v;
        }
        norm = (float) Math.sqrt(norm);
        if (norm > 0) {
            for (int i = 0; i < vector.length; i++) {
                vector[i] /= norm;
            }
        }

        return vector;
    }

    /**
     * 生成随机归一化向量（降级方案）
     *
     * 在模型加载失败时使用，保证系统不因为 Embedding 不可用而崩溃。
     * 虽然检索质量会下降，但整个流程可以继续运行。
     * 生成的向量经过 L2 归一化，模长为 1，避免数值异常。
     *
     * @return 归一化的随机向量
     */
    private float[] generateFallbackVector() {
        int dim = ragConfig.getEmbedding().getDimension();
        float[] vector = new float[dim];
        java.util.Random random = new java.util.Random();
        float norm = 0f;
        // 生成 [-1, 1] 范围内的随机数
        for (int i = 0; i < dim; i++) {
            vector[i] = random.nextFloat() * 2 - 1;
            norm += vector[i] * vector[i];
        }
        // L2 归一化，保证模长为 1
        norm = (float) Math.sqrt(norm);
        if (norm > 0) {
            for (int i = 0; i < dim; i++) {
                vector[i] /= norm;
            }
        }
        return vector;
    }

    /**
     * 销毁服务（Spring 容器关闭时自动执行）
     * 按依赖顺序关闭：分词器 → 推理会话 → ONNX 环境
     */
    @PreDestroy
    public void destroy() {
        try {
            if (tokenizer != null) {
                tokenizer.close();
            }
            if (session != null) {
                session.close();
            }
            if (env != null) {
                env.close();
            }
            // 清理临时文件
            for (Path tempFile : tempFiles) {
                try {
                    Files.deleteIfExists(tempFile);
                } catch (IOException e) {
                    log.warn("清理临时文件失败: {}", tempFile, e);
                }
            }
            tempFiles.clear();
            log.info("Embedding 服务已关闭");
        } catch (Exception e) {
            log.error("Embedding 服务关闭失败", e);
        }
    }
}