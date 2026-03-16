#!/usr/bin/env python3
import requests
import sys


def test_siliconflow_key(api_key: str):
    """测试硅基流动API Key"""
    url = "https://api.siliconflow.cn/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    print(f"测试Key: {api_key[:10]}...")

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            models = resp.json()
            print("✅ API Key有效！")
            print(f"可用模型数: {len(models.get('data', []))}")
            print("\n推荐模型:")
            for m in models.get('data', [])[:5]:
                print(f"  - {m.get('id')}")
            return True

        elif resp.status_code == 401:
            print("❌ API Key无效或已过期")
            return False

        elif resp.status_code == 403:
            print("❌ API Key被禁止访问")
            print(f"错误详情: {resp.text[:200]}")
            return False

        else:
            print(f"❌ 未知错误: {resp.status_code}")
            print(resp.text[:200])
            return False

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        key = input("请输入硅基流动API Key: ").strip()
    else:
        key = sys.argv[1]

    test_siliconflow_key(key)