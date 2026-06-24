import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# 确保脚本能够找到当前目录下的 .env 文件
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
env_path = os.path.join(project_root, '.env')

load_dotenv(dotenv_path=env_path)

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "https://token.sensenova.cn/v1")
model = os.getenv("LLM_MODEL", "sensenova-6.7-flash-lite")

print("="*40)
print(f"Base URL : {base_url}")
print(f"Model    : {model}")
print(f"API Key  : {'已加载 (Loaded)' if api_key else '未加载 (Not Found)'}")
print("="*40)

if not api_key:
    print("❌ 错误：未能在 .env 环境中找到 LLM_API_KEY")
    sys.exit(1)

client = OpenAI(
    base_url=base_url,
    api_key=api_key,
)

try:
    print("\n[请求中] 正在发送测试请求到 API...")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "你好，请用一句话做一个简短的测试回复。"}],
        timeout=15 
    )
    print("\n✅ 请求成功！以下是模型的回复内容：")
    print("-" * 40)
    print(response.choices[0].message.content)
    print("-" * 40)
except Exception as e:
    print(f"\n❌ 请求失败，发生错误：\n{e}")
