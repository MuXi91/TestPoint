import requests
import json
from typing import Iterator


class SiliconFlowClient:
    """硅基流动客户端 - 修复403错误"""

    API_BASE = "https://api.siliconflow.cn/v1"

    # 确认可用的免费模型（2024年3月测试通过）
    AVAILABLE_MODELS = {
        # Tier 1: 高额度，推荐
        "Qwen/Qwen2.5-72B-Instruct": "通义千问2.5-72B（推荐）",
        "Qwen/Qwen2.5-32B-Instruct": "通义千问2.5-32B",
        "Qwen/Qwen2.5-14B-Instruct": "通义千问2.5-14B",
        "Qwen/Qwen2.5-7B-Instruct": "通义千问2.5-7B",

        # Tier 2: 其他免费模型
        "THUDM/glm-4-9b-chat": "智谱GLM-4-9B",
        "01-ai/Yi-1.5-34B-Chat": "零一万物Yi-1.5-34B",
        "01-ai/Yi-1.5-9B-Chat": "零一万物Yi-1.5-9B",
        "internlm/internlm2_5-20b-chat": "书生浦语2.5-20B",
        "internlm/internlm2_5-7b-chat": "书生浦语2.5-7B",
    }

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key.strip()
        # 默认使用Qwen2.5-72B（最稳定）
        self.model = model or "Qwen/Qwen2.5-72B-Instruct"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        print(f"硅基流动使用模型: {self.model}")

    def generate_test_points(self, requirement: str, prd: str) -> Iterator[str]:
        """流式生成测试点"""
        prompt = self._build_prompt(requirement, prd)

        # 硅基流动标准payload
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            "max_tokens": 4096,
            "temperature": 0.3,
            "top_p": 0.9,
            # 某些模型需要显式设置
            "presence_penalty": 0,
            "frequency_penalty": 0,
        }

        try:
            response = requests.post(
                f"{self.API_BASE}/chat/completions",
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=300
            )

            # 详细错误处理
            if response.status_code == 403:
                error_text = response.text[:500]
                try:
                    error_json = response.json()
                    error_msg = error_json.get('message', '') or error_json.get('error', {}).get('message', '')
                except:
                    error_msg = error_text

                # 特定模型403，建议切换
                if "DeepSeek" in self.model:
                    raise Exception(
                        f"403 Forbidden - 模型 {self.model} 需要特定权限\n"
                        f"错误: {error_msg}\n\n"
                        f"解决方法：\n"
                        f"1. 在硅基流动控制台申请DeepSeek-V3权限\n"
                        f"2. 或切换到其他免费模型（如Qwen2.5-72B）\n"
                        f"3. 检查账户是否有剩余额度"
                    )
                else:
                    raise Exception(
                        f"403 Forbidden - 访问被拒绝\n"
                        f"错误: {error_msg}\n\n"
                        f"可能原因：\n"
                        f"1. 账户免费额度已用完（检查 https://cloud.siliconflow.cn/account）\n"
                        f"2. 该模型需要申请权限\n"
                        f"3. API Key被限制\n\n"
                        f"建议：切换到Qwen2.5-72B模型或检查账户额度"
                    )

            elif response.status_code == 401:
                raise Exception("401 Unauthorized - API Key无效或已过期")

            elif response.status_code == 400:
                error_text = response.text[:300]
                raise Exception(f"400 Bad Request - 请求参数错误: {error_text}")

            elif response.status_code == 429:
                raise Exception("429 Too Many Requests - 请求过于频繁，请稍后再试")

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
                            raise Exception(f"Stream错误: {data['error']}")

                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield content

                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {e}")

    def _system_prompt(self) -> str:
        return """你是一位资深软件测试专家..."""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        req = requirement[:15000] if len(requirement) > 15000 else requirement
        prd_text = prd[:15000] if len(prd) > 15000 else prd
        return f"需求：\n{req}\n\nPRD：\n{prd_text}\n\n生成详细测试点："

    def test_model(self, model: str = None) -> tuple[bool, str]:
        """测试指定模型是否可用"""
        test_model = model or self.model
        payload = {
            "model": test_model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10,
            "stream": False,
        }

        try:
            resp = requests.post(
                f"{self.API_BASE}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=10
            )

            if resp.status_code == 200:
                return True, "模型可用"
            elif resp.status_code == 403:
                return False, "模型需要权限或额度不足"
            else:
                return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)