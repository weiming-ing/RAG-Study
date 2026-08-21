import urllib.request, json

token = "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VySWQiOjEsInVzZXJuYW1lIjoiYWRtaW4iLCJzdWIiOiJhZG1pbiIsImV4cCI6MTc4NzMxMTI2OX0.1Yd9IBW0CaY7V1bGZnhS3tGfD10gaG2_esAyJbTk4GT2YrRiWPgYcP3W1Pxtq2-tFilkoz4sMqa1EJj7V7Laog"

# 1. 查看所有分组对话
req = urllib.request.Request("http://localhost:8002/api/conversations/grouped", headers={"Authorization": f"Bearer {token}"})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read().decode("utf-8"))
print("=== 所有分组对话记录 ===")
for item in data.get("data", []):
    print(f'  user_id={item.get("user_id")}, username="{item.get("username")}", total_count={item.get("total_count")}')

# 2. 查看所有系统用户
req2 = urllib.request.Request("http://localhost:8002/api/sys/user/page?pageNum=1&pageSize=200", headers={"Authorization": f"Bearer {token}"})
try:
    resp2 = urllib.request.urlopen(req2, timeout=10)
    data2 = json.loads(resp2.read().decode("utf-8"))
    print("\n=== 系统用户列表 ===")
    if "data" in data2 and "records" in data2["data"]:
        for user in data2["data"]["records"]:
            print(f'  id={user.get("id")}, username="{user.get("username")}"')
    else:
        print(json.dumps(data2, ensure_ascii=False, indent=2)[:500])
except Exception as e:
    print(f"\n获取用户列表失败: {e}")

# 3. 查询 userId=456 的对话记录
req3 = urllib.request.Request("http://localhost:8002/api/conversations?pageNum=1&pageSize=50&userId=456", headers={"Authorization": f"Bearer {token}"})
try:
    resp3 = urllib.request.urlopen(req3, timeout=10)
    data3 = json.loads(resp3.read().decode("utf-8"))
    total = data3.get("data", {}).get("total", 0)
    print(f"\n=== userId=456 的对话记录: total={total} ===")
    if total > 0:
        for rec in data3["data"]["records"]:
            q = rec.get("question", "")[:60]
            print(f'  id={rec.get("id")}, question="{q}"')
    else:
        print("  没有找到 userId=456 的对话记录")
except Exception as e:
    print(f"\n查询userId=456失败: {e}")

# 4. 查询大范围 userId 看看有没有接近456的记录
for uid in [400, 450, 455, 456, 457, 460, 500]:
    try:
        r = urllib.request.Request(f"http://localhost:8002/api/conversations?pageNum=1&pageSize=5&userId={uid}", headers={"Authorization": f"Bearer {token}"})
        resp = urllib.request.urlopen(r, timeout=10)
        d = json.loads(resp.read().decode("utf-8"))
        t = d.get("data", {}).get("total", 0)
        if t > 0:
            print(f"\n  userId={uid} 有 {t} 条记录!")
    except:
        pass