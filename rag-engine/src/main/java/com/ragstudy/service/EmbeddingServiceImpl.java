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

@Service
public class EmbeddingServiceImpl implements EmbeddingService {

    private static final Logger log = LoggerFactory.getLogger(EmbeddingServiceImpl.class);

    private final RagConfig ragConfig;
    private OrtEnvironment env;
    private OrtSession session;
    private HuggingFaceTokenizer tokenizer;
    private boolean initialized = false;

    public EmbeddingServiceImpl(RagConfig ragConfig) {
        this.ragConfig = ragConfig;
    }

    @PostConstruct
    public void init() {
        log.info("初始化 Embedding 服务...");
        try {
            RagConfig.EmbeddingConfig embeddingConfig = ragConfig.getEmbedding();
            String modelPath = resolvePath(embeddingConfig.getModelPath());
            String tokenizerPath = resolvePath(embeddingConfig.getTokenizerPath());

            log.info("加载 ONNX 模型: {}", modelPath);
            env = OrtEnvironment.getEnvironment();
            OrtSession.SessionOptions options = new OrtSession.SessionOptions();
            options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
            session = env.createSession(modelPath, options);

            log.info("加载分词器: {}", tokenizerPath);
            tokenizer = HuggingFaceTokenizer.newInstance(Path.of(tokenizerPath));

            initialized = true;
            log.info("Embedding 服务初始化完成 - 模型: {}, 向量维度: {}",
                    modelPath, embeddingConfig.getDimension());
        } catch (Exception e) {
            log.error("Embedding 服务初始化失败: {}", e.getMessage(), e);
            initialized = false;
        }
    }

    private String resolvePath(String path) {
        if (path.startsWith("classpath:")) {
            String classpathPath = path.substring("classpath:".length());
            try {
                return new ClassPathResource(classpathPath).getFile().getAbsolutePath();
            } catch (IOException e) {
                throw new RuntimeException("无法解析 classpath 资源: " + classpathPath, e);
            }
        }
        return path;
    }

    @Override
    public int getDimension() {
        return ragConfig.getEmbedding().getDimension();
    }

    @Override
    public float[] embed(String text) {
        if (!initialized) {
            log.warn("Embedding 服务未初始化，使用随机向量作为降级方案");
            return generateFallbackVector();
        }

        try {
            return doEmbed(text);
        } catch (Exception e) {
            log.error("向量化失败: text={}", text.substring(0, Math.min(50, text.length())), e);
            throw new RuntimeException("向量化失败: " + e.getMessage(), e);
        }
    }

    @Override
    public List<float[]> embedBatch(List<String> texts) {
        if (!initialized) {
            log.warn("Embedding 服务未初始化，批量使用随机向量作为降级方案");
            return texts.stream().map(t -> generateFallbackVector()).collect(java.util.stream.Collectors.toList());
        }

        List<float[]> results = new ArrayList<>();
        for (String text : texts) {
            try {
                results.add(doEmbed(text));
            } catch (Exception e) {
                log.error("批量向量化失败: text={}", text.substring(0, Math.min(50, text.length())), e);
                results.add(new float[ragConfig.getEmbedding().getDimension()]);
            }
        }
        return results;
    }

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

    private float[] meanPooling(OnnxTensor outputTensor, int seqLength, long[] attentionMask) throws OrtException {
        long[] shape = outputTensor.getInfo().getShape();
        int hiddenSize = (int) shape[2];
        FloatBuffer buffer = outputTensor.getFloatBuffer();

        float[] pooled = new float[hiddenSize];
        for (int j = 0; j < hiddenSize; j++) {
            float sum = 0f;
            int count = 0;
            for (int i = 0; i < seqLength; i++) {
                if (attentionMask[i] == 1) {
                    sum += buffer.get(i * hiddenSize + j);
                    count++;
                }
            }
            pooled[j] = count > 0 ? sum / count : 0f;
        }

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

    private float[] extractVector(OnnxTensor outputTensor) throws OrtException {
        long[] shape = outputTensor.getInfo().getShape();
        int dim = (int) shape[1];
        float[] vector = new float[dim];
        FloatBuffer buffer = outputTensor.getFloatBuffer();
        buffer.get(vector);

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

    private float[] generateFallbackVector() {
        int dim = ragConfig.getEmbedding().getDimension();
        float[] vector = new float[dim];
        java.util.Random random = new java.util.Random();
        float norm = 0f;
        for (int i = 0; i < dim; i++) {
            vector[i] = random.nextFloat() * 2 - 1;
            norm += vector[i] * vector[i];
        }
        norm = (float) Math.sqrt(norm);
        if (norm > 0) {
            for (int i = 0; i < dim; i++) {
                vector[i] /= norm;
            }
        }
        return vector;
    }

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
            log.info("Embedding 服务已关闭");
        } catch (Exception e) {
            log.error("Embedding 服务关闭失败", e);
        }
    }
}