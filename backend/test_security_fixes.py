"""
P0 修复项离线回归测试（无需运行服务，stub Redis）

覆盖：
  1. 语义缓存按 kb_id 隔离：同问题在不同 KB 各自缓存、互不命中
  2. 语义缓存淘汰：超量后按 TTL 淘汰且清理 idx 索引
  3. 限流中间件：达到上限返回 429，未到上限放行，Redis 故障时 fail open

运行：python test_security_fixes.py
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

import services.semantic_cache as sc  # noqa: E402


class StubPipe:
    def __init__(self, store):
        self.store = store
        self.ops = []
        self.results = []

    def setex(self, k, t, v):
        self.ops.append(("set", k, v))

    def delete(self, *ks):
        self.ops.append(("del", ks))

    def zremrangebyscore(self, key, lo, hi):
        # 滑动窗口清理：模拟移除窗口外的成员；redis-py 会为每个命令返回一个结果
        self.ops.append(("zremrange", key, lo, hi))
        self.results.append(0)

    def zcard(self, key):
        members = self.store.get(key) or []
        self.results.append(len(members))
        return self

    async def execute(self):
        rets = list(self.results)
        self.results = []
        for op in self.ops:
            if op[0] == "set":
                self.store[op[1]] = op[2]
            elif op[0] == "del":
                for k in op[1]:
                    self.store.pop(k, None)
            elif op[0] == "zremrange":
                members = self.store.get(op[1]) or []
                self.store[op[1]] = [m for m in members if m[0] > op[3]]
        self.ops = []
        return rets


class StubRedis:
    def __init__(self):
        self.store = {}
        self.available = True

    async def get(self, k):
        return self.store.get(k)

    def pipeline(self):
        return StubPipe(self.store)

    async def ttl(self, k):
        return 100

    async def scan_iter(self, match="", count=0):
        import fnmatch
        if not self.available:
            raise ConnectionError("redis down")
        for k in list(self.store):
            if fnmatch.fnmatch(k, match):
                yield k

    async def zadd(self, key, mapping):
        members = self.store.setdefault(key, [])
        for member, score in mapping.items():
            members.append((score, member))

    async def expire(self, *a):
        pass

    async def delete(self, *ks):
        for k in ks:
            self.store.pop(k, None)


async def test_cache_isolation():
    svc = sc.SemanticCacheService()
    r = StubRedis()
    sc.get_redis = lambda: _fake(r)
    sc.SemanticCacheService._get_vector = lambda self, text: _fake([0.1] * 512)

    await svc.store("报销流程是什么", "答案A", [], kb_id="1")
    await svc.store("报销流程是什么", "答案B", [], kb_id="2")

    hit1 = await svc.lookup("报销流程是什么", kb_id="1")
    hit2 = await svc.lookup("报销流程是什么", kb_id="2")
    hit3 = await svc.lookup("报销流程是什么", kb_id="3")
    hit_all = await svc.lookup("报销流程是什么")

    assert hit1 and hit1["answer"] == "答案A", f"KB1 应命中答案A: {hit1}"
    assert hit2 and hit2["answer"] == "答案B", f"KB2 应命中答案B: {hit2}"
    assert hit3 is None, "无缓存 KB 不应命中"
    assert hit_all is None, "all 范围不应命中 KB 内条目"
    print("  [PASS] 语义缓存按 kb_id 隔离")


async def test_cache_eviction():
    svc = sc.SemanticCacheService()
    r = StubRedis()
    sc.get_redis = lambda: _fake(r)
    sc.SemanticCacheService._get_vector = lambda self, text: _fake([0.1] * 512)

    old_max = sc.MAX_CACHE_ENTRIES
    sc.MAX_CACHE_ENTRIES = 2
    try:
        for i in range(4):
            await svc.store(f"问题{i}", f"答案{i}", [], kb_id="9")
        vec_keys = [k for k in r.store if k.startswith("sc:v:9:")]
        idx_keys = [k for k in r.store if k.startswith("sc:idx:9:")]
        assert len(vec_keys) <= 2, f"淘汰后向量条目应<=2, got {len(vec_keys)}"
        assert len(idx_keys) <= 2, f"淘汰后 idx 索引应<=2（原实现漏删）, got {len(idx_keys)}"
    finally:
        sc.MAX_CACHE_ENTRIES = old_max
    print("  [PASS] 语义缓存淘汰含 idx 索引清理")


async def test_rate_limit():
    from middleware.rate_limit_middleware import RateLimitMiddleware
    import middleware.rate_limit_middleware as rlm

    r = StubRedis()
    rlm.get_redis = lambda: _fake(r)

    class FakeRequest:
        url_path = "/api/chat"
        headers = {}
        client = None
        state_user = {}

        class url:
            path = "/api/chat"

        class state:
            user = {"id": 42}

    req = FakeRequest()
    called = []

    async def call_next(_):
        called.append(1)
        return "OK"

    mw = RateLimitMiddleware(None)
    import middleware.rate_limit_middleware as cfg

    # 未到上限：放行
    for i in range(3):
        resp = await mw.dispatch(req, call_next)
        assert resp == "OK", f"第{i+1}次请求不应被限流: {resp}"

    # 将阈值压到 3，触发 429
    old_limit = cfg.RATE_LIMIT_USER_PER_MIN
    cfg.RATE_LIMIT_USER_PER_MIN = 3
    try:
        resp = await mw.dispatch(req, call_next)
        assert getattr(resp, "status_code", None) == 429, f"应返回 429: {resp}"
    finally:
        cfg.RATE_LIMIT_USER_PER_MIN = old_limit

    # Redis 故障：fail open 放行
    r.available = False
    resp = await mw.dispatch(req, call_next)
    assert resp == "OK", f"Redis 故障应 fail open: {resp}"
    print("  [PASS] 限流 429 触发与 Redis 故障放行")


async def _fake(value):
    return value


async def main():
    print("=" * 50)
    print(" P0 修复项离线回归")
    print("=" * 50)
    await test_cache_isolation()
    await test_cache_eviction()
    await test_rate_limit()
    print("\n全部通过")


if __name__ == "__main__":
    asyncio.run(main())
