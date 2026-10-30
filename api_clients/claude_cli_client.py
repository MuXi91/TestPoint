"""
Claude CLI客户端封装
通过调用本地 Claude Code 命令生成测试点
"""

import json
import subprocess
import sys
import os
import re
from pathlib import Path
from typing import Iterator, Optional
from api_clients.prompts import SYSTEM_PROMPT, build_user_prompt


def load_claude_config_from_zshrc() -> dict:
    """
    从 ~/.zshrc 读取 Claude 配置
    返回: {"base_url": "...", "token": "..."}
    """
    config = {"base_url": None, "token": None}

    zshrc_path = Path.home() / ".zshrc"
    if not zshrc_path.exists():
        return config

    try:
        with open(zshrc_path, 'r') as f:
            content = f.read()

        # 匹配 AI_BASE_URL="xxx" 或 export AI_BASE_URL="xxx"
        base_url_match = re.search(r'(?:export\s+)?AI_BASE_URL\s*=\s*["\']([^"\']+)["\']', content)
        if base_url_match:
            config["base_url"] = base_url_match.group(1)

        # 匹配 AI_TOKEN="xxx"
        token_match = re.search(r'(?:export\s+)?AI_TOKEN\s*=\s*["\']([^"\']+)["\']', content)
        if token_match:
            config["token"] = token_match.group(1)

    except Exception as e:
        print(f"[DEBUG] 读取 zshrc 失败: {e}")

    return config


class ClaudeCLIClient:
    """Claude CLI客户端 - 用于测试点生成"""

    SUPPORTED_MODELS = [
        "glm-5",
        "kimi-k2.5",
        "claude-opus-4-6",
        "claude-sonnet-4-6"
    ]

    def __init__(self, model: str = "glm-5"):
        self.model = model
        self.config = load_claude_config_from_zshrc()
        print(f"[DEBUG] Claude CLI 使用模型: {self.model}")
        print(f"[DEBUG] 从 zshrc 加载配置: base_url={self.config['base_url']}")

    def test_connection(self) -> tuple[bool, str]:
        """测试Claude CLI连接是否正常"""
        cmd = [
            "claude",
            "--model", self.model,
            "-p", "OK",
            "--output-format", "stream-json",
            "--verbose"
        ]

        env = os.environ.copy()
        if self.config.get("base_url"):
            env["ANTHROPIC_BASE_URL"] = self.config["base_url"]
        if self.config.get("token"):
            env["ANTHROPIC_AUTH_TOKEN"] = self.config["token"]

        print(f"[DEBUG] 测试连接命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                stdin=subprocess.DEVNULL,
                timeout=120
            )

            output = result.stdout

            if output and ('"type":"system"' in output or '"type":"result"' in output or '"type":"assistant"' in output):
                for line in output.strip().split('\n'):
                    try:
                        data = json.loads(line)
                        if data.get("type") == "result":
                            if not data.get("is_error"):
                                return True, f"连接成功 (模型: {self.model})"
                            else:
                                return False, f"API错误: {data.get('result', '')[:100]}"
                    except:
                        pass
                return True, f"连接成功 (模型: {self.model})"

            if result.returncode != 0:
                return False, f"Claude CLI 返回错误: {result.stderr[:200] if result.stderr else '未知错误'}"

            return False, f"响应格式异常"

        except subprocess.TimeoutExpired:
            return False, "连接超时 (120秒)"
        except FileNotFoundError:
            return False, "未找到 claude 命令"
        except Exception as e:
            return False, f"异常: {str(e)}"

    def generate_test_points(self, requirement: str, prd: str) -> Iterator[str]:
        """
        流式生成测试点 - 兼容 SiliconFlowClient 接口
        """
        prompt = self._build_prompt(requirement, prd)

        cmd = [
            "claude",
            "--model", self.model,
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose"
        ]

        env = os.environ.copy()
        if self.config.get("base_url"):
            env["ANTHROPIC_BASE_URL"] = self.config["base_url"]
        if self.config.get("token"):
            env["ANTHROPIC_AUTH_TOKEN"] = self.config["token"]

        print(f"[DEBUG] 调用 Claude CLI (模型: {self.model})...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                stdin=subprocess.DEVNULL,
                timeout=600  # 10分钟超时
            )

            print(f"[DEBUG] CLI返回码: {result.returncode}")

            output = result.stdout

            if not output:
                raise Exception("无输出")

            if result.returncode != 0 and not ('"type":"assistant"' in output or '"type":"result"' in output):
                raise Exception(f"Claude CLI 错误: {result.stderr[:200] if result.stderr else '未知错误'}")

            # 解析输出
            full_content = ""
            for line in output.strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg_type = data.get("type", "unknown")

                    if msg_type == "assistant":
                        message = data.get("message", {})
                        content_blocks = message.get("content", [])
                        for block in content_blocks:
                            if isinstance(block, dict) and block.get("type") == "text":
                                full_content += block.get("text", "")

                    elif msg_type == "result":
                        if data.get("is_error"):
                            raise Exception(f"API错误: {data.get('result', '')}")

                except json.JSONDecodeError:
                    if line and not line.startswith('{'):
                        full_content += line

            # 限制大小
            if len(full_content) > 100000:
                full_content = full_content[:100000]

            print(f"[DEBUG] 生成完成，共 {len(full_content)} 字符")

            # 流式返回（模拟）
            yield full_content

        except subprocess.TimeoutExpired:
            raise Exception("请求超时 (10分钟)")
        except FileNotFoundError:
            raise Exception("未找到 claude 命令")
        except Exception as e:
            if "Claude CLI" in str(e) or "API错误" in str(e) or "请求超时" in str(e):
                raise
            raise Exception(f"调用失败: {str(e)}")

    def _build_prompt(self, requirement: str, prd: str) -> str:
        return f"{SYSTEM_PROMPT}\n\n{build_user_prompt(requirement, prd)}"

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT
