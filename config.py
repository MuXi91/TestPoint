import os
import json
import re
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
        "claude_cli": {
            "name": "Claude CLI (本地)",
            "url": "",
            "key_format": "无需API Key",
            "free_quota": "本地调用",
            "default_model": "glm-5",
            "recommended_models": [
                "glm-5",
                "kimi-k2.5",
                "claude-sonnet-4-6",
                "claude-opus-4-6",
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

    # 环境变量名映射（大写，符合 Unix 惯例）
    ENV_VAR_MAP = {
        "siliconflow": "SILICONFLOW_KEY",
        "deepseek": "DEEPSEEK_KEY",
        "zhipu": "ZHIPU_KEY",
        "openrouter": "OPENROUTER_KEY",
    }

    def __init__(self):
        self.siliconflow_key = ""
        self.deepseek_key = ""
        self.zhipu_key = ""
        self.openrouter_key = ""
        self.default_ai = "siliconflow"  # 默认使用硅基流动
        self.siliconflow_model = "Qwen/Qwen2.5-72B-Instruct"  # 默认模型（推理能力最强）
        self.deepseek_model = "deepseek-chat"
        self.zhipu_model = "glm-4-flash"
        self.openrouter_model = "google/gemma-2-9b-it:free"
        self.claude_cli_model = "glm-5"  # Claude CLI 默认模型
        # 加载配置（优先级：.zshrc > 配置文件）
        self.load()  # 第一步：从配置文件读取（作为默认值）
        self._load_from_env()  # 第二步：从环境变量/.zshrc读取（覆盖配置文件）

    def _load_from_zshrc(self):
        """从 ~/.zshrc 文件读取环境变量"""
        zshrc_path = Path.home() / ".zshrc"
        if not zshrc_path.exists():
            return {}

        result = {}
        try:
            with open(zshrc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 匹配 export VAR="value" 或 export VAR='value' 格式
            for provider, env_var in self.ENV_VAR_MAP.items():
                # 匹配 export SILICONFLOW_KEY="sk-xxx" 或 export SILICONFLOW_KEY='sk-xxx'
                pattern = rf'export\s+{env_var}\s*=\s*["\']([^"\']+)["\']'
                match = re.search(pattern, content)
                if match:
                    result[env_var] = match.group(1)
                    print(f"✅ 从 ~/.zshrc 加载 {env_var}")
        except Exception as e:
            print(f"警告：读取 ~/.zshrc 失败: {e}")

        return result

    def _load_from_env(self):
        """从系统环境变量或 ~/.zshrc 读取 API Key（覆盖配置文件的值）"""
        # 先尝试从系统环境变量读取
        env_values = {}
        for provider, env_var in self.ENV_VAR_MAP.items():
            # 尝试读取环境变量（支持大小写）
            value = os.environ.get(env_var) or os.environ.get(env_var.lower())
            if value:
                env_values[env_var] = value.strip()
                print(f"✅ 从系统环境变量加载 {env_var}")

        # 如果系统环境变量没有，尝试从 ~/.zshrc 读取
        if len(env_values) < len(self.ENV_VAR_MAP):
            zshrc_values = self._load_from_zshrc()
            for env_var, value in zshrc_values.items():
                if env_var not in env_values:
                    env_values[env_var] = value

        # 设置属性（覆盖已有值）
        for provider, env_var in self.ENV_VAR_MAP.items():
            if env_var in env_values:
                setattr(self, f"{provider}_key", env_values[env_var])

    def load(self):
        """从配置文件加载（仅补充环境变量未设置的值）"""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 只更新环境变量中未设置的值（避免覆盖环境变量）
                for key, value in data.items():
                    if hasattr(self, key) and not getattr(self, key):
                        setattr(self, key, value)

            except Exception as e:
                print(f"警告：配置文件读取失败: {e}")

    def save(self):
        """保存配置到文件（保存当前内存中的值）"""
        try:
            data = {
                "siliconflow_key": self.siliconflow_key,
                "deepseek_key": self.deepseek_key,
                "zhipu_key": self.zhipu_key,
                "openrouter_key": self.openrouter_key,
                "default_ai": self.default_ai,
                "siliconflow_model": self.siliconflow_model,
                "deepseek_model": self.deepseek_model,
                "zhipu_model": self.zhipu_model,
                "openrouter_model": self.openrouter_model,
                "claude_cli_model": self.claude_cli_model,
            }

            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"警告：配置文件保存失败: {e}")

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
        elif self.default_ai == "claude_cli":
            from api_clients.claude_cli_client import ClaudeCLIClient
            return ClaudeCLIClient(model=self.claude_cli_model)
        return None

    def get_key(self, provider: str) -> str:
        """获取指定提供商的API Key"""
        return getattr(self, f"{provider}_key", "")

    def set_key(self, provider: str, key: str):
        """设置指定提供商的API Key"""
        setattr(self, f"{provider}_key", key)

    def get_env_status(self) -> dict:
        """获取环境变量加载状态（调试用）"""
        status = {}
        for provider, env_var in self.ENV_VAR_MAP.items():
            env_value = os.environ.get(env_var) or os.environ.get(env_var.lower())
            config_value = getattr(self, f"{provider}_key", "")
            status[provider] = {
                "env_var": env_var,
                "from_env": bool(env_value),
                "has_value": bool(config_value),
                "value_preview": config_value[:10] + "..." if config_value else None
            }
        return status