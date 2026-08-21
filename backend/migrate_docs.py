import os
import glob
import httpx
import asyncio
from pathlib import Path

JAVA_BACKEND = "http://localhost:8002"
DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"


async def upload_file(client: httpx.AsyncClient, filepath: str) -> dict:
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = f.read()

    files = {"file": (filename, content, "text/markdown")}

    resp = await client.post(
        f"{JAVA_BACKEND}/api/internal/knowledge/upload",
        files=files,
        data={"department": "企业制度", "category": "管理规范"},
    )
    return resp.json()


async def main():
    files = glob.glob(str(DOCS_DIR / "*.md"))
    if not files:
        print("没有找到 .md 文件")
        return

    print(f"找到 {len(files)} 个文件，开始上传到 Java 后端...\n")

    timeout = httpx.Timeout(300.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        success = 0
        fail = 0
        for fpath in sorted(files):
            filename = os.path.basename(fpath)
            size = os.path.getsize(fpath)
            print(f"上传中: {filename} ({size} bytes)...", end=" ", flush=True)
            try:
                result = await upload_file(client, fpath)
                if result.get("code") == 0:
                    doc = result.get("data", {})
                    print(f"✓ 成功 (id={doc.get('id')}, chunks={doc.get('totalChunks')})")
                    success += 1
                else:
                    print(f"✗ 失败: {result.get('message', '未知错误')}")
                    fail += 1
            except Exception as e:
                print(f"✗ 异常: {e}")
                fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败")


if __name__ == "__main__":
    asyncio.run(main())