import requests
import json
from typing import Iterator


class OpenRouterClient:
    """OpenRouter客户端 - 2024年3月可用模型"""

    API_BASE = "https://openrouter.ai/api/v1"

    # 2024年3月确认可用的免费模型（OpenRouter免费模型经常变动）
    FREE_MODELS = {
        # 当前可用的（需要实时检查）
        "google/gemma-2-9b-it:free": "Gemma 2 9B (免费)",
        "microsoft/phi-3-medium-128k-instruct:free": "Phi-3 Medium (免费)",
        "mistralai/mistral-7b-instruct:free": "Mistral 7B (免费)",
        "huggingfaceh4/zephyr-7b-beta:free": "Zephyr 7B (免费)",
        "nousresearch/hermes-2-pro-mistral-7b:free": "Hermes 2 Pro 7B (免费)",
    }

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key.strip()
        # 默认使用第一个可用模型
        self.model = model or "google/gemma-2-9b-it:free"

        # 确保有:free后缀
        if ":free" not in self.model and ":paid" not in self.model:
            self.model = self.model + ":free"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "TestPointGenerator",
        }
        print(f"OpenRouter使用模型: {self.model}")

    def generate_test_points(self, requirement: str, prd: str) -> Iterator[str]:
        """流式生成测试点"""
        prompt = self._build_prompt(requirement, prd)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True,
        }

        try:
            response = requests.post(
                f"{self.API_BASE}/chat/completions",
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=300
            )

            # 处理404错误 - 模型不存在
            if response.status_code == 404:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')

                # 获取当前可用免费模型建议
                available = self._get_current_free_models()
                available_str = "\n".join([f"  - {m}" for m in available[:5]])

                raise Exception(
                    f"404 Not Found - 模型不存在或已下线\n"
                    f"当前模型: {self.model}\n"
                    f"错误信息: {error_msg}\n\n"
                    f"当前可用的免费模型建议:\n{available_str}\n\n"
                    f"请访问 https://openrouter.ai/models?sort=pricing_high_to_low 查看最新免费模型"
                )

            elif response.status_code == 401:
                raise Exception("API Key无效")
            elif response.status_code == 429:
                raise Exception("请求过于频繁")
            elif response.status_code == 402:
                raise Exception("免费额度已用完，需要付费")

            response.raise_for_status()

            # 处理流式响应
            for line in response.iter_lines():
                if not line:
                    continue

                line_str = line.decode('utf-8')

                if line_str.startswith('data: '):
                    data_str = line_str[6:]

                    if data_str == '[DONE]':
                        break

                    try:
                        data = json.loads(data_str)

                        if 'error' in data:
                            raise Exception(f"API错误: {data['error']}")

                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield content

                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {e}")

    def _get_current_free_models(self) -> list:
        """获取当前API返回的可用模型列表"""
        try:
            resp = requests.get(
                f"{self.API_BASE}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get('data', []):
                    model_id = m.get('id', '')
                    pricing = m.get('pricing', {})
                    # 只返回免费模型
                    if pricing.get('prompt', 1) == 0 and pricing.get('completion', 1) == 0:
                        models.append(model_id)
                return models
        except:
            pass
        return list(self.FREE_MODELS.keys())

    def _system_prompt(self) -> str:
        return """你是一位资深软件测试专家..."""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        req = requirement[:12000] if len(requirement) > 12000 else requirement
        prd_text = prd[:12000] if len(prd) > 12000 else prd
        return f"需求：\n{req}\n\nPRD：\n{prd_text}\n\n生成测试点："