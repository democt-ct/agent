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
        
        prompt = (
            f"我要去{location}游玩，请推荐8-10个值得去的地点。\n"
            "要求：\n"
            "1. 必须包含3-4个当地最值得去的经典地标，这些是任何人都不该错过的\n"
            "2. 同时推荐3-4个小众或本地特色地点，丰富体验层次\n"
            "3. 每个地点说明：名称、类型（自然/历史/美食/文艺等）、独特亮点（一句话点明为什么值得去）\n"
            "4. 经典地点要说清楚其标志性意义，小众地点要说明独特之处"
        )

        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3.2",
            messages=[
                {"role": "system", "content": (
                    "你是一个在当地生活多年的资深旅行达人，熟悉每个城市的隐藏宝藏。"
                    "你的推荐风格具体、有温度，会说明地点的独特之处而非套话，"
                    "擅长挖掘游客手册上找不到的本地体验。"
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
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
