# ---- Build Stage ----
FROM maven:3.9-eclipse-temurin-21-alpine AS build

WORKDIR /app

# 先复制 pom.xml 利用 Docker 缓存层加速构建
COPY pom.xml ./
RUN mvn dependency:go-offline -B

# 复制源码并构建
COPY src ./src
RUN mvn package -DskipTests -B

# ---- Run Stage ----
# 用 Ubuntu（glibc）而不是 alpine：ONNX Runtime 原生库依赖 glibc
# （libstdc++.so.6 与 ld-linux-x86-64.so.2），alpine + gcompat 不可靠
FROM eclipse-temurin:21-jre-noble

WORKDIR /app

# 创建数据目录；补 curl 供 compose 健康检查使用
RUN mkdir -p /app/data/bm25_index \
    && apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 jar
# 注意：ONNX 模型已随 src/main/resources 打进 jar（约 90MB），
# EmbeddingServiceImpl.resolvePath() 会从 classpath 解压到临时文件加载，
# 因此不要再单独 COPY 一份 models 目录——那会让镜像白白多出 90MB。
COPY --from=build /app/target/*.jar app.jar

EXPOSE 8002

# JVM 参数：允许 native access（ONNX Runtime 需要）
ENTRYPOINT ["java", \
    "--enable-native-access=ALL-UNNAMED", \
    "-Xms512m", "-Xmx2g", \
    "-Dspring.profiles.active=docker", \
    "-jar", "app.jar"]