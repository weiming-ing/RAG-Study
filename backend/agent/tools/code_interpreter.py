import asyncio
import os
import tempfile
import traceback

CODE_TIMEOUT = 30
CODE_MAX_OUTPUT = 4000

FORBIDDEN_IMPORTS = {
    "os", "subprocess", "sys", "shutil", "importlib",
    "__builtins__", "eval", "exec", "compile", "open",
    "pty", "fcntl", "resource", "signal", "socket",
    "http", "urllib", "ftplib", "telnetlib", "smtplib",
}


async def _code_execute(code: str, language: str = "python") -> str:
    if language != "python":
        return f"目前仅支持 Python 代码执行，不支持 {language}。"

    code = code.strip()
    if not code:
        return "未提供要执行的代码。"

    if len(code) > 10000:
        return "代码过长（超过 10000 字符），请精简后再试。"

    for keyword in FORBIDDEN_IMPORTS:
        if f"import {keyword}" in code or f"from {keyword}" in code:
            return f"禁止导入模块: {keyword}。出于安全考虑，代码执行环境不允许导入系统级模块。"

    if "import " in code or "from " in code:
        allowed_imports = {"math", "statistics", "json", "re", "datetime", "collections",
                          "itertools", "functools", "random", "decimal", "fractions",
                          "hashlib", "base64", "csv", "string", "textwrap", "typing",
                          "dataclasses", "enum", "copy", "pprint", "operator",
                          "calendar", "time", "uuid", "heapq", "bisect", "array",
                          "struct", "io", "pathlib", "tempfile", "zipfile", "gzip",
                          "numpy", "pandas", "matplotlib", "sympy", "scipy"}
        lines = code.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                parts = line.split()
                if len(parts) >= 2:
                    module = parts[1].split(".")[0]
                    if module not in allowed_imports:
                        return f"不允许导入模块: {module}。允许的模块: {', '.join(sorted(allowed_imports))}"

    safe_builtins = {
        "abs": abs, "all": all, "any": any, "ascii": ascii,
        "bin": bin, "bool": bool, "bytearray": bytearray,
        "bytes": bytes, "callable": callable, "chr": chr,
        "complex": complex, "dict": dict, "dir": dir,
        "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "frozenset": frozenset,
        "getattr": getattr, "hasattr": hasattr, "hash": hash,
        "hex": hex, "id": id, "int": int, "isinstance": isinstance,
        "issubclass": issubclass, "iter": iter, "len": len,
        "list": list, "map": map, "max": max, "min": min,
        "next": next, "object": object, "oct": oct, "ord": ord,
        "pow": pow, "print": print, "range": range, "repr": repr,
        "reversed": reversed, "round": round, "set": set,
        "slice": slice, "sorted": sorted, "str": str, "sum": sum,
        "super": super, "tuple": tuple, "type": type, "vars": vars,
        "zip": zip, "True": True, "False": False, "None": None,
        "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "KeyError": KeyError,
        "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError,
        "__import__": __import__,
    }
    safe_globals = {"__builtins__": safe_builtins}

    try:
        import math
        import random
        import json
        import re
        import datetime
        import collections
        import itertools
        import functools
        import statistics
        import decimal
        import fractions
        import hashlib
        import base64
        import csv
        import string
        import textwrap
        import typing
        import dataclasses
        import enum
        import copy
        import pprint
        import operator

        safe_globals.update({
            "math": math, "random": random, "json": json, "re": re,
            "datetime": datetime, "collections": collections,
            "itertools": itertools, "functools": functools,
            "statistics": statistics, "decimal": decimal,
            "fractions": fractions, "hashlib": hashlib,
            "base64": base64, "csv": csv, "string": string,
            "textwrap": textwrap, "typing": typing,
            "dataclasses": dataclasses, "enum": enum,
            "copy": copy, "pprint": pprint, "operator": operator,
        })

        try:
            import numpy as np
            safe_globals["numpy"] = np
            safe_globals["np"] = np
        except ImportError:
            pass

        try:
            import pandas as pd
            safe_globals["pandas"] = pd
            safe_globals["pd"] = pd
        except ImportError:
            pass

    except Exception:
        pass

    output_buffer = []

    def custom_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(a) for a in args) + end
        output_buffer.append(text)
        if len("".join(output_buffer)) > CODE_MAX_OUTPUT:
            raise RuntimeError("输出超出限制")

    safe_globals["print"] = custom_print

    try:
        compiled = compile(code, "<agent_code>", "exec")
        await asyncio.wait_for(
            asyncio.to_thread(exec, compiled, safe_globals),
            timeout=CODE_TIMEOUT,
        )
        result = "".join(output_buffer)
        if not result.strip():
            last_expr = code.strip().split("\n")[-1]
            if not last_expr.startswith(("print", "import", "from", "def", "class", "if", "for", "while", "try", "with", "#")):
                try:
                    expr_result = await asyncio.wait_for(
                        asyncio.to_thread(eval, last_expr, safe_globals),
                        timeout=CODE_TIMEOUT,
                    )
                    result = str(expr_result)
                except Exception:
                    pass
        return result[:CODE_MAX_OUTPUT] if result.strip() else "代码执行完成，无输出。"

    except asyncio.TimeoutError:
        return f"代码执行超时（{CODE_TIMEOUT} 秒），请检查是否有死循环或过于耗时的操作。"
    except Exception as e:
        return f"代码执行出错:\n{traceback.format_exc()}"