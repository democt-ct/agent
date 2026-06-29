from playwright.sync_api import sync_playwright
import time

def test_xiaohongshu():
    with sync_playwright() as p:
        # 启动浏览器，headless=True 不显示界面
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # 访问小红书首页
            print("正在访问小红书...")
            page.goto("https://www.xiaohongshu.com", timeout=30000)
            print(f"页面标题: {page.title()}")
            
            # 尝试搜索
            print("尝试搜索 'agent开发进展'...")
            # 小红书搜索框可能需要先点击搜索图标
            # 这里尝试直接访问搜索页面
            search_url = "https://www.xiaohongshu.com/search_result?keyword=agent%E5%BC%80%E5%8F%91%E8%BF%9B%E5%B1%95&source=web_search_result_notes"
            page.goto(search_url, timeout=30000)
            time.sleep(3)  # 等待加载
            
            print(f"搜索页面标题: {page.title()}")
            
            # 获取搜索结果（简单提取标题）
            results = page.query_selector_all('div.title')
            if results:
                print(f"找到 {len(results)} 个结果:")
                for i, result in enumerate(results[:5]):  # 只显示前5个
                    text = result.inner_text()
                    print(f"{i+1}. {text}")
            else:
                # 尝试其他选择器
                results = page.query_selector_all('a.title')
                if results:
                    print(f"找到 {len(results)} 个结果:")
                    for i, result in enumerate(results[:5]):
                        text = result.inner_text()
                        print(f"{i+1}. {text}")
                else:
                    print("未找到搜索结果，可能页面结构已更改")
                    
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            browser.close()
            print("测试完成")

if __name__ == "__main__":
    test_xiaohongshu()