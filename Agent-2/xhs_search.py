from playwright.sync_api import sync_playwright
import time
import urllib.parse

def search_xiaohongshu(keyword):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 直接打开搜索页面
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_search_result_notes"

        print(f"正在打开小红书搜索: {keyword}")
        print("请在浏览器中完成登录，登录后搜索结果会自动显示")
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        
        # 等待用户操作（登录、查看结果）
        print("\n浏览器已打开，请操作完成后按 Enter 键继续...")
        print("(如果需要登录，请先扫码登录，然后搜索结果会自动显示)\n")
        
        # 等待用户按Enter
        input("按 Enter 键保存结果并关闭浏览器...")

        # 截图保存
        page.screenshot(path="xhs_search_result.png", full_page=False)
        print(f"\n已保存截图: xhs_search_result.png")

        # 获取搜索结果
        print("\n" + "=" * 50)
        print(f"搜索结果：{keyword}")
        print("=" * 50)

        selectors = [
            "section.note-item a.title span",
            "div.note-item .title",
            "a.cover span.title",
            "a[class*='title']"
        ]
        
        found = False
        for sel in selectors:
            notes = page.locator(sel).all()
            if notes:
                print(f"\n找到 {len(notes)} 条笔记:\n")
                for i, note in enumerate(notes[:20], 1):
                    try:
                        title = note.inner_text()
                        if title.strip():
                            print(f"  {i}. {title.strip()}")
                            found = True
                    except:
                        pass
                if found:
                    break

        if not found:
            print("\n页面文本内容:")
            body_text = page.locator("body").inner_text()
            print(body_text[:3000])

        print("\n正在关闭浏览器...")
        time.sleep(2)
        browser.close()
        print("完成!")

if __name__ == "__main__":
    search_xiaohongshu("成都美食")
