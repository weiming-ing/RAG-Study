#!/usr/bin/env python
"""依赖一致性校验：代码里 import 的包 ↔ requirements 声明的包

为什么需要这个脚本：
  * 镜像里少一个包 → 容器启动即崩，而且是客户现场才发现；
  * 镜像里多一个包 → 离线交付包白白大出好几 GB（torch 一个就 490MB+）；
  * 两者都靠人工核对，一定会出错。

检查项：
  1. [FAIL] 代码顶层 import 的第三方包，未在 requirements.txt 声明
  2. [WARN] requirements.txt 声明但全仓库无人 import（可能是死依赖）
  3. [FAIL] requirements-fallback.txt 中的包被「顶层」import
     —— 可选依赖必须延迟到函数内导入，否则精简镜像启动即崩
  4. [INFO] 已从主依赖移除的重型包清单（精简收益）

用法：
    python deploy/verify-deps.py
退出码：0 = 通过，1 = 存在失败项
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

# 发行包名 → 实际 import 名（其余按 PEP 503 规则把 - 换成 _）
DIST_TO_IMPORT = {
    "python-dotenv": "dotenv",
    "python-multipart": "multipart",
    "python-jose": "jose",
    "uvicorn": "uvicorn",
    "bcrypt": "bcrypt",
    "pydantic": "pydantic",
}

# 声明了但确实不会被本项目代码 import 的包（附原因）
IMPLICIT_ONLY = {
    "python-multipart": "Starlette 解析 multipart 表单（文档上传）时自行导入",
}

# 代码直接 import、但有意不在 requirements 中声明：由上游依赖传递提供。
# 显式声明版本区间可能与上游约束冲突，反而导致 pip 解析失败。
TRANSITIVE_PROVIDED = {
    "starlette": "由 fastapi 传递提供（fastapi 自带 compatibility 区间约束）",
}

# 已从主依赖移除的重型包（用于展示精简收益，若重新出现在顶层 import 则报错）
HEAVY_REMOVED = {
    "langchain", "langchain_community", "langchain_text_splitters",
    "chromadb", "sentence_transformers", "torch", "transformers",
    "pypdf", "PyPDF2", "docx", "docx2txt", "rank_bm25",
}

results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def parse_requirements(path: Path) -> list[str]:
    """解析 requirements 文件，返回发行包名列表（去掉版本、extras、注释）。"""
    names: list[str] = []
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!\[\s;]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name.lower())
    return names


def import_name(dist: str) -> str:
    return DIST_TO_IMPORT.get(dist, dist.replace("-", "_"))


def local_modules() -> set[str]:
    """backend 内的本地模块名（这些不属于第三方依赖）。"""
    mods: set[str] = set()
    for p in BACKEND.iterdir():
        if p.is_dir() and (p / "__init__.py").exists():
            mods.add(p.name)
        elif p.suffix == ".py":
            mods.add(p.stem)
    return mods


def collect_imports(tree: ast.Module) -> tuple[set[str], set[str]]:
    """返回 (顶层导入的顶层模块名, 函数/类内部导入的顶层模块名)。

    模块级的 if / try / with 视为顶层（例如 `if __name__ == "__main__": import uvicorn`）。
    """
    top: set[str] = set()
    nested: set[str] = set()

    def root_of(node: ast.Import | ast.ImportFrom) -> set[str]:
        names = set()
        if isinstance(node, ast.Import):
            names = {a.name.split(".")[0] for a in node.names}
        elif node.level == 0 and node.module:
            names = {node.module.split(".")[0]}
        return names

    def walk(node: ast.AST, is_top: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                (top if is_top else nested).update(root_of(child))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(child, False)
            elif isinstance(child, (ast.If, ast.Try, ast.With, ast.AsyncWith)):
                walk(child, is_top)  # 模块级的分支保持顶层语义
            else:
                walk(child, is_top)

    walk(tree, True)
    return top, nested


def main() -> int:
    main_reqs = parse_requirements(BACKEND / "requirements.txt")
    fallback_reqs = parse_requirements(BACKEND / "requirements-fallback.txt")

    if not main_reqs:
        print(f"[ERROR] 未找到或无法解析 {BACKEND / 'requirements.txt'}")
        return 1

    locals_ = local_modules()
    stdlib = set(sys.stdlib_module_names)

    top_imports: set[str] = set()
    nested_imports: set[str] = set()
    parse_errors: list[str] = []
    skipped: list[str] = []

    for py in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        # 与 backend/.dockerignore 保持一致：开发期临时脚本不进交付镜像，
        # 因此不纳入依赖校验（它们可能依赖仅本机安装的包）。
        # 注意不要误伤 __init__.py —— 包初始化文件里同样有真实 import。
        if (py.name.startswith("_") and not py.name.startswith("__")) \
                or py.name.startswith("test_"):
            skipped.append(str(py.relative_to(REPO_ROOT)))
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as exc:
            parse_errors.append(f"{py.relative_to(REPO_ROOT)}: {exc}")
            continue
        t, n = collect_imports(tree)
        top_imports |= t
        nested_imports |= n

    third_party_top = {m for m in top_imports if m not in stdlib and m not in locals_}
    third_party_all = {m for m in (top_imports | nested_imports)
                       if m not in stdlib and m not in locals_}

    declared_imports = {import_name(d) for d in main_reqs}
    fallback_imports = {import_name(d) for d in fallback_reqs}

    print("=" * 70)
    print("依赖一致性校验（backend）")
    print("=" * 70)
    print(f"  主依赖声明        : {len(main_reqs)} 个")
    print(f"  可选依赖声明      : {len(fallback_reqs)} 个")
    print(f"  第三方顶层 import : {len(third_party_top)} 个")
    print(f"  第三方全部 import : {len(third_party_all)} 个")

    print("\n--- 1) 顶层 import 是否都有声明 ---")
    missing = sorted(third_party_top - declared_imports - fallback_imports
                     - set(TRANSITIVE_PROVIDED))
    for m, why in sorted(TRANSITIVE_PROVIDED.items()):
        if m in third_party_top:
            print(f"  [OK]   {m} —— 传递提供（{why}）")
    if missing:
        for m in missing:
            print(f"  [FAIL] 未声明: {m}")
            record("FAIL", f"缺少依赖声明: {m}", "容器启动会 ModuleNotFoundError")
    else:
        print("  [OK] 顶层 import 全部有声明")
        record("PASS", "顶层 import 全部有声明")

    print("\n--- 2) 是否存在死依赖（声明但无人 import） ---")
    dead = []
    for d in main_reqs:
        imp = import_name(d)
        if imp in third_party_all:
            continue
        if d in IMPLICIT_ONLY:
            print(f"  [OK]   {d} —— 隐式必需（{IMPLICIT_ONLY[d]}）")
            continue
        dead.append(d)
        print(f"  [WARN] {d} —— 全仓库未见 import，疑似死依赖")
        record("WARN", f"疑似死依赖: {d}", "确认无用后可从 requirements.txt 移除")
    if not dead:
        print("  [OK] 无死依赖")
        record("PASS", "无死依赖")

    print("\n--- 3) 可选依赖是否被顶层 import（会破坏精简镜像） ---")
    leak = sorted(fallback_imports & third_party_top)
    if leak:
        for m in leak:
            print(f"  [FAIL] {m} 被顶层 import —— 精简镜像启动即崩")
            record("FAIL", f"可选依赖被顶层导入: {m}", "改为函数内延迟导入")
    else:
        print("  [OK] 可选依赖均为延迟导入")
        record("PASS", "可选依赖均为延迟导入")

    print("\n--- 4) 已移除的重型包是否又被引入 ---")
    reintroduced = sorted(HEAVY_REMOVED & third_party_top)
    if reintroduced:
        for m in reintroduced:
            print(f"  [FAIL] {m} 重新出现在顶层 import")
            record("FAIL", f"重型包重新被引入: {m}", "会显著增大交付镜像")
    else:
        print("  [OK] 未被重新引入")
        record("PASS", "重型包未被重新引入")

    if fallback_reqs:
        print("\n--- 5) 可选依赖清单（默认不安装） ---")
        for d in fallback_reqs:
            print(f"  - {d}  (import: {import_name(d)})")

    if parse_errors:
        print("\n--- 无法解析的文件 ---")
        for e in parse_errors:
            print(f"  [WARN] {e}")
            record("WARN", f"语法解析失败: {e}")

    if skipped:
        print(f"\n--- 已跳过 {len(skipped)} 个开发期脚本（不进交付镜像） ---")
        for s in skipped:
            print(f"  - {s}")

    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]
    print("\n" + "=" * 70)
    print(f"汇总：通过 {len([r for r in results if r[0] == 'PASS'])} / "
          f"失败 {len(failed)} / 警告 {len(warned)}")
    if failed:
        print("\n失败项：")
        for _, name, detail in failed:
            print(f"  - {name}（{detail}）")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
