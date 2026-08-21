"""
下载 BGE 中文嵌入模型 (ONNX 版本)
模型来源: Xenova/bge-small-zh-v1.5
运行方式: python download_model.py
"""
import os
import sys

MODEL_ID = "Xenova/bge-small-zh-v1.5"
TARGET_DIR = os.path.dirname(os.path.abspath(__file__))

FILES_TO_DOWNLOAD = [
    "onnx/model.onnx",
    "onnx/model.onnx_data",
    "onnx/model_fp16.onnx",
    "onnx/model_fp16.onnx_data",
    "onnx/model_q4.onnx",
    "onnx/model_q4.onnx_data",
    "onnx/model_q4f16.onnx",
    "onnx/model_q4f16.onnx_data",
    "onnx/model_quantized.onnx",
    "onnx/model_quantized.onnx_data",
]


def download_with_huggingface_hub():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    os.makedirs(os.path.join(TARGET_DIR, "onnx"), exist_ok=True)

    for filename in FILES_TO_DOWNLOAD:
        local_path = os.path.join(TARGET_DIR, filename)
        if os.path.exists(local_path):
            print(f"已存在, 跳过: {filename}")
            continue

        print(f"下载中: {filename} ...")
        hf_hub_download(
            repo_id=MODEL_ID,
            filename=filename,
            local_dir=TARGET_DIR,
            local_dir_use_symlinks=False,
        )
        print(f"完成: {filename}")

    print("\n所有模型文件下载完成!")


def download_with_requests():
    try:
        import requests
    except ImportError:
        print("请先安装 requests: pip install requests")
        sys.exit(1)

    BASE_URL = f"https://huggingface.co/{MODEL_ID}/resolve/main"

    os.makedirs(os.path.join(TARGET_DIR, "onnx"), exist_ok=True)

    for filename in FILES_TO_DOWNLOAD:
        local_path = os.path.join(TARGET_DIR, filename)
        if os.path.exists(local_path):
            print(f"已存在, 跳过: {filename}")
            continue

        url = f"{BASE_URL}/{filename}"
        print(f"下载中: {filename} ...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = downloaded / total_size * 100
                    print(f"\r{filename}: {percent:.1f}%", end="")
        print(f"\n完成: {filename}")

    print("\n所有模型文件下载完成!")


if __name__ == "__main__":
    print(f"模型: {MODEL_ID}")
    print(f"目标目录: {TARGET_DIR}\n")

    download_with_huggingface_hub()