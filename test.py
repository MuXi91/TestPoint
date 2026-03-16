#!/usr/bin/env python3
import requests
import sys


def test_openrouter_free(key: str):
    """测试OpenRouter当前免费模型"""
    print("=" * 60)
    print("测试OpenRouter免费模型")
    print("=" * 60)

    # 可能免费的模型列表
    candidates = [
        "google/gemma-2-9b-it:free",
        "microsoft/phi-3-medium-128k-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "huggingfaceh4/zephyr-7b-beta:free",
        "gryphe/mythomax-l2-13b:free",
        "nousresearch/hermes-2-pro-mistral-7b:free",
    ]

    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "HTTP-Referer": "https://localhost",
        "X-Title": "Test",
    }

    working = []

    for model in candidates:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10,
        }

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )

            if resp.status_code == 200:
                print(f"✅ {model:50s} 可用")
                working.append(model)
            elif resp.status_code == 404:
                print(f"❌ {model:50s} 不存在/已下线")
            else:
                print(f"⚠️  {model:50s} HTTP {resp.status_code}")

        except Exception as e:
            print(f"💥 {model:50s} 错误: {e}")

    print(f"\n当前可用免费模型 ({len(working)}个):")
    for m in working:
        print(f"  - {m}")

    return working


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_current.py <openrouter_key>")
        sys.exit(1)

    test_openrouter_free(sys.argv[1])