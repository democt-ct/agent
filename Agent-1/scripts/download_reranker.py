"""下载并测试 Reranker 模型 - 多源下载"""

import os
import sys

def try_download_from_source(model_name, source_name, hf_endpoint=None):
    """尝试从指定源下载模型"""
    print(f"\n尝试从 {source_name} 下载...")
    
    if hf_endpoint:
        os.environ["HF_ENDPOINT"] = hf_endpoint
    elif "HF_ENDPOINT" in os.environ:
        del os.environ["HF_ENDPOINT"]
    
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(model_name, max_length=512)
        return model
    except Exception as e:
        print(f"  失败: {str(e)[:100]}")
        return None

def main():
    print("=" * 50)
    print("Reranker 模型下载工具（多源）")
    print("=" * 50)
    
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        print("错误: 未安装 sentence-transformers")
        print("请运行: pip install sentence-transformers")
        sys.exit(1)
    
    model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # 尝试多个下载源
    sources = [
        ("HuggingFace 官方", "https://huggingface.co", None),
        ("HuggingFace 镜像", None, "https://hf-mirror.com"),
        ("ModelScope 镜像", None, "https://modelscope.cn"),
    ]
    
    model = None
    for source_name, hf_endpoint, _ in sources:
        model = try_download_from_source(model_name, source_name, hf_endpoint)
        if model:
            print(f"✓ 从 {source_name} 下载成功！")
            break
    
    if not model:
        print("\n✗ 所有下载源都失败了")
        print("\n请尝试以下方法：")
        print("1. 检查网络连接")
        print("2. 使用 VPN 访问 HuggingFace")
        print("3. 手动下载模型到 ~/.cache/huggingface/hub/")
        print(f"   模型地址: https://huggingface.co/{model_name}")
        sys.exit(1)
    
    # 测试
    print("\n正在测试模型...")
    pairs = [
        ("高血压不能吃什么", "高血压患者应避免高盐食物，每日盐摄入量不超过5克"),
        ("高血压不能吃什么", "今天天气很好"),
    ]
    
    try:
        scores = model.predict(pairs)
        print(f"✓ 测试通过！")
        print(f"  相关文本得分: {scores[0]:.4f}")
        print(f"  不相关文本得分: {scores[1]:.4f}")
        
        if scores[0] > scores[1]:
            print("✓ 模型能够正确区分相关和不相关文本")
        else:
            print("⚠ 模型区分能力可能有问题")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("Reranker 模型已就绪！")
    print("启动服务时会自动加载此模型。")
    print("=" * 50)

if __name__ == "__main__":
    main()
