# 企业内部知识库 RAG 客服助手 - 环境搭建指南

## 1. 系统要求
- Python 3.10+
- Ollama（用于本地 LLM 推理）
- Windows / Linux / macOS

## 2. 安装步骤

### 2.1 安装 Ollama
# Windows: 从 https://ollama.com 下载安装包
# 安装后拉取模型：
ollama pull qwen2.5:7b
ollama pull nomic-embed-text   # embedding 模型

### 2.2 安装 Python 依赖
cd backend
pip install -r requirements.txt

### 2.3 启动后端
cd backend
python main.py

### 2.4 访问前端
浏览器打开 http://localhost:8000