import os

# ================= 配置区 =================
# 你可以在这里直接填入，或者通过环境变量传入
openai_api_key = os.getenv("LLM_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b")

os.environ["OPENAI_API_KEY"] = openai_api_key
openai_api_base = "https://api-inference.modelscope.cn/v1/"
# ==========================================

def query_tourist_spots(location):
    print(f"正在连接大模型 查询 {location} 的游玩攻略，请稍候...\n")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base
        )
        
        prompt = f"我要在{location}玩，请帮我查一下有哪些值得去的旅游地点？给出一个简单的推荐列表及特色。"
        
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3.2", # 或者 qwen-plus, qwen-turbo
            messages=[
                {"role": "system", "content": "你是一个专业的旅游规划助手，擅长推荐当地特色景点、美食和游玩路线。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        print("================ 模型回复 ================\n")
        print(response.choices[0].message.content)
        print("\n==========================================")
        
    except ImportError:
        print("提示：缺少 openai 依赖库")
        print("请在终端运行: pip install openai")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    target_location = "绵阳"
    query_tourist_spots(target_location)
