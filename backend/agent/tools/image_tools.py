from config import DATA_DIR
from pathlib import Path


async def _image_generate(prompt: str, size: str = "512x512") -> str:
    return (
        f"图片生成请求已记录:\n"
        f"  提示词: {prompt}\n"
        f"  尺寸: {size}\n\n"
        "当前版本暂不支持直接生成图片。如需此功能，可以:\n"
        "1. 集成 OpenAI DALL-E API\n"
        "2. 集成 Stability AI API\n"
        "3. 使用本地 Stable Diffusion 模型\n\n"
        "请在配置中设置相应的 API Key 后启用此功能。"
    )


async def _image_analyze(file_path: str, question: str = "") -> str:
    path = Path(file_path)
    if not path.is_absolute():
        path = DATA_DIR / "documents" / file_path

    if not path.exists():
        return f"图片文件不存在: {file_path}"

    suffix = path.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"):
        return f"不支持的文件格式: {suffix}。支持的图片格式: png, jpg, jpeg, gif, bmp, webp, svg"

    try:
        from PIL import Image
        img = Image.open(str(path))
        info = {
            "格式": img.format,
            "尺寸": f"{img.size[0]} x {img.size[1]} 像素",
            "模式": img.mode,
            "文件大小": f"{path.stat().st_size / 1024:.1f} KB",
        }

        if hasattr(img, "info") and img.info:
            for key, value in img.info.items():
                if isinstance(value, (str, int, float)):
                    info[key] = str(value)

        lines = [f"图片分析: {path.name}"]
        for key, value in info.items():
            lines.append(f"  {key}: {value}")

        if question:
            lines.append(f"\n用户问题: {question}")
            lines.append("当前版本暂不支持基于 AI 的图像内容识别。如需此功能，可以集成以下服务:")
            lines.append("  - OpenAI Vision API (GPT-4V)")
            lines.append("  - 百度 AI 图像识别")
            lines.append("  - 本地部署的视觉模型")

        return "\n".join(lines)

    except ImportError:
        return "读取图片需要安装 Pillow 库。请运行: pip install Pillow"
    except Exception as e:
        return f"分析图片失败: {e}"