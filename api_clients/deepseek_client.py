import requests
import json
from typing import Iterator
from api_clients.prompts import SYSTEM_PROMPT, build_user_prompt


class DeepSeekClient:
    """DeepSeek官方API - 完全免费"""
    API_BASE = "https://api.deepseek.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_test_points(self, requirement: str, prd: str) -> Iterator[str]:
        prompt = self._build_prompt(requirement, prd)

        payload = {
            "model": "deepseek-chat",  # DeepSeek-V3
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 8192,
            "stream": True,
            "top_p": 0.85,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.3,
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

    def _build_prompt(self, requirement: str, prd: str) -> str:
        return build_user_prompt(requirement, prd)
