import requests
import json
from typing import Iterator


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
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
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
        return """你是专业的QA测试工程师，擅长测试点设计。
输出要求：
- 使用XMind兼容的Markdown格式
- 层级：#产品模块 -> ##功能点 -> ###测试场景 -> -测试步骤
- 覆盖：功能测试、边界值测试、正常场景、异常场景、安卓兼容、web端兼容、iOS兼容、h5兼容
- 每个测试点标注优先级（P0/P1/P2）"""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        return f"""基于以下需求生成测试点：

需求文档：
{requirement[:50000]}

产品设计PRD：
{prd[:50000]}

请输出结构化的测试点，使用Markdown层级格式，便于导入思维导图工具。"""