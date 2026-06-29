import asyncio
import httpx
from urllib.parse import quote

async def main():
    query = "成都美食攻略 本地人推荐"
    url = f"https://www.bing.com/search?q={quote(query)}&setlang=zh-cn"
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        
        # 保存HTML以便分析
        with open("bing_debug.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        
        print(f"已保存 HTML 到 bing_debug.html ({len(resp.text)} bytes)")
        
        # 检查是否有搜索结果相关的class
        import re
        patterns_to_check = [
            'class="b_algo"',
            'class="b_results"',
            'class="b_ans"',
            'class="b_algoList"',
            'id="b_results"',
            'class="result"',
            'class="search"',
        ]
        
        for p in patterns_to_check:
            count = len(re.findall(p, resp.text))
            if count > 0:
                print(f"找到: {p} ({count} 次)")
        
        # 找所有h2标签看看
        h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', resp.text[:50000], re.DOTALL)
        print(f"\nh2标签数量: {len(h2_matches)}")
        for i, h2 in enumerate(h2_matches[:5], 1):
            clean = re.sub(r'<[^>]+>', '', h2).strip()[:80]
            print(f"  {i}. {clean}")

if __name__ == "__main__":
    asyncio.run(main())
