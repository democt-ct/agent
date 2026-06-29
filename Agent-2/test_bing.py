import asyncio
import httpx
import re
from urllib.parse import quote

_BING_URL = "https://www.bing.com/search"
_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html_tags(html: str) -> str:
    return _TAG_RE.sub(' ', html).strip()

def _extract_bing_results(html: str, max_results: int):
    results = []
    algo_positions = [m.start() for m in re.finditer(r'class="b_algo"', html)]
    
    for i, pos in enumerate(algo_positions[:max_results]):
        end_pos = algo_positions[i + 1] if i + 1 < len(algo_positions) else len(html)
        block = html[pos:end_pos]

        title_m = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_m:
            continue
        url = title_m.group(1)
        title = _strip_html_tags(title_m.group(2))

        snippet = ""
        for pat in [r'<p[^>]*>(.*?)</p>', r'class="b_caption"[^>]*>(.*?)</div>']:
            m = re.search(pat, block, re.DOTALL)
            if m:
                snippet = _strip_html_tags(m.group(1))
                if len(snippet) > 10:
                    break

        if title:
            results.append({"title": title, "snippet": snippet, "url": url})

    return results

async def test_search(query: str):
    url = f"{_BING_URL}?q={quote(query)}&setlang=zh-cn"
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应长度: {len(resp.text)}")
        
        results = _extract_bing_results(resp.text, 5)
        print(f"提取到 {len(results)} 条结果\n")
        
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']}")
            print(f"   URL: {r['url'][:60]}...")
            if r['snippet']:
                print(f"   摘要: {r['snippet'][:100]}...")
            print()

async def main():
    queries = [
        "成都美食攻略 本地人推荐",
        "成都 必吃美食 评价",
        "成都旅游攻略 美食篇",
    ]
    
    for q in queries:
        print(f"=" * 50)
        print(f"搜索: {q}")
        print("=" * 50)
        await test_search(q)

if __name__ == "__main__":
    asyncio.run(main())
