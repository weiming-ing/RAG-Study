import httpx

SEARCH_TIMEOUT = 15.0


async def _web_search(query: str, num_results: int = 5) -> str:
    try:
        search_url = "https://html.duckduckgo.com/html/"
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            resp = await client.post(
                search_url,
                data={"q": query, "kl": "cn-zh"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
            if resp.status_code != 200:
                return f"搜索请求失败 (HTTP {resp.status_code})"

            html = resp.text

            from html.parser import HTMLParser

            class DDGParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.in_result = False
                    self.in_title = False
                    self.in_snippet = False
                    self.current_title = ""
                    self.current_snippet = ""
                    self.current_link = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                        self.in_result = True
                        self.current_title = ""
                        self.current_snippet = ""
                        self.current_link = attrs_dict.get("href", "")
                    if self.in_result and tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
                        self.in_snippet = True

                def handle_endtag(self, tag):
                    if self.in_result and tag == "a":
                        if self.current_title:
                            self.results.append({
                                "title": self.current_title.strip(),
                                "snippet": self.current_snippet.strip(),
                                "link": self.current_link,
                            })
                        self.in_result = False
                        self.in_title = False
                        self.in_snippet = False

                def handle_data(self, data):
                    if self.in_result and not self.in_snippet:
                        self.current_title += data
                    if self.in_snippet:
                        self.current_snippet += data

            parser = DDGParser()
            parser.feed(html)

            results = parser.results[:num_results]

            if not results:
                return f"未找到与 '{query}' 相关的搜索结果。"

            lines = [f"搜索 '{query}' 的结果:"]
            for i, r in enumerate(results, 1):
                lines.append(f"\n{i}. {r['title']}")
                lines.append(f"   {r['snippet'][:200]}")
                if r['link']:
                    lines.append(f"   链接: {r['link']}")

            return "\n".join(lines)

    except httpx.TimeoutException:
        return f"搜索超时：'{query}' 的搜索请求超过了 {SEARCH_TIMEOUT} 秒。"
    except Exception as e:
        return f"搜索失败: {e}"