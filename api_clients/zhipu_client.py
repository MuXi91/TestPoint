import requests
import json
import time
import jwt
from typing import Iterator


class ZhipuClient:
    """智谱AI GLM-4 - 免费额度"""
    API_BASE = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, api_key: str):
        # 智谱使用API Key格式：id.secret
        self.api_key = api_key
        self.headers = {
            "Authorization": self._generate_token(),
            "Content-Type": "application/json"
        }

    def _generate_token(self) -> str:
        """生成JWT Token"""
        try:
            id, secret = self.api_key.split('.')
        except ValueError:
            raise ValueError("智谱API Key格式应为：id.secret")

        payload = {
            "api_key": id,
            "exp": int(time.time()) + 3600,
            "timestamp": int(time.time())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        return f"Bearer {token}"

    def generate_test_points(self, requirement: str, prd: str) -> Iterator[str]:
        prompt = self._build_prompt(requirement, prd)

        # 刷新token
        self.headers["Authorization"] = self._generate_token()

        payload = {
            "model": "glm-4-flash",  # 免费版
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "stream": True
        }

        response = requests.post(
            f"{self.API_BASE}/chat/completions",
            headers=self.headers,
            json=payload,
            stream=True,
            timeout=300
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk['choices'][0]['delta'].get('content'):
                            yield chunk['choices'][0]['delta']['content']
                    except:
                        continue

    def _system_prompt(self) -> str:
        return """你是测试专家，从需求中提取测试点。使用Markdown层级结构输出。"""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        return f"需求：\n{requirement}\n\nPRD：\n{prd}\n\n生成测试点思维导图："