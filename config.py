import os
import json
from pathlib import Path


class Config:
    CONFIG_FILE = Path.home() / ".test_generator_config.json"

    # 免费模型配置
    FREE_MODELS = {
        "siliconflow": {
            "name": "硅基流动 (稳定)",
            "url": "https://cloud.siliconflow.cn",
            "key_format": "sk-xxxxxx",
            "free_quota": "2000万Tokens",
            "default_model": "Qwen/Qwen2.5-72B-Instruct",  # 改用Qwen，DeepSeek容易403
            "recommended_models": [
                "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
                "Qwen/Qwen2.5-72B-Instruct",  # 最稳定，推荐
                "Qwen/Qwen2.5-32B-Instruct",
                "THUDM/GLM-Z1-32B-0414",
                "01-ai/Yi-1.5-34B-Chat",
            ]
        },
        "openrouter": {
            "name": "OpenRouter (备用)",
            "url": "https://openrouter.ai",
            "key_format": "sk-or-v1-xxxxxx",
            "free_quota": "无限（限流）",
            "default_model": "meta-llama/llama-3.1-70b-instruct:free",
            "recommended_models": [
                "meta-llama/llama-3.1-70b-instruct:free",
                "google/gemma-2-9b-it:free",
                "microsoft/phi-3-medium-128k-instruct:free",
            ]
        }
    }

    def __init__(self):
        self.siliconflow_key = "sk-sabegakghnfzjeglfvejsfnvzthbvsfzwcphnjxkqjdalszp"
        self.deepseek_key = ""
        self.zhipu_key = ""
        self.openrouter_key = "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"
        self.default_ai = "siliconflow"  # 默认使用硅基流动
        self.siliconflow_model = "Qwen/Qwen2.5-72B-Instruct"  # 默认模型
        self.deepseek_model = "deepseek-chat"
        self.zhipu_model = "glm-4-flash"
        self.openrouter_model = "google/gemma-2-9b-it:free"
        self.load()


    def load(self):
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.__dict__.update(data)

    def save(self):
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "siliconflow_key": self.siliconflow_key,
                "deepseek_key": self.deepseek_key,
                "zhipu_key": self.zhipu_key,
                "openrouter_key": self.openrouter_key,
                "default_ai": self.default_ai
            }, f, indent=2, ensure_ascii=False)

    def get_ai_client(self):
        """获取配置的AI客户端"""
        if self.default_ai == "siliconflow" and self.siliconflow_key:
            from api_clients.siliconflow_client import SiliconFlowClient
            return SiliconFlowClient(self.siliconflow_key, self.siliconflow_model)
        elif self.default_ai == "deepseek" and self.deepseek_key:
            from api_clients.deepseek_client import DeepSeekClient
            return DeepSeekClient(self.deepseek_key)
        elif self.default_ai == "zhipu" and self.zhipu_key:
            from api_clients.zhipu_client import ZhipuClient
            return ZhipuClient(self.zhipu_key)
        elif self.default_ai == "openrouter" and self.openrouter_key:
            from api_clients.openrouter_client import OpenRouterClient
            return OpenRouterClient(self.openrouter_key, self.openrouter_model)
        return None

    def get_key(self, provider: str) -> str:
        """获取指定提供商的API Key"""
        return getattr(self, f"{provider}_key", "")

    def set_key(self, provider: str, key: str):
        """设置指定提供商的API Key"""
        setattr(self, f"{provider}_key", key)