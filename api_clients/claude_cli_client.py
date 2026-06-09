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
        """构建提示词"""
        req = requirement[:20000] if len(requirement) > 20000 else requirement
        prd_text = prd[:20000] if len(prd) > 20000 else prd

        return """# 角色定位
        你是一位拥有10年+经验的资深软件测试专家，擅长根据需求文档提取完善的测试点用来生成测试用例。
        你的任务是：基于提供的PRD/需求文档，生成一份结构清晰、覆盖全面、可直接落地的测试点文档。

        # 项目背景
        是一个在线盲盒/开箱（Online Mystery Box）娱乐平台。它结合了电商、抽奖与游戏化元素，允许用户以远低于商品实际价值的价格参与抽奖，
        有机会获得高价值的实物或虚拟商品。该项目主要围绕“充值、开箱、置换、对战”构建了一套完整的 GamiFication（游戏化）玩法
        1. 传统盲盒开箱。选择盲盒：平台上拥有数百种不同主题的盲盒；概率抽奖：支付对应盲盒的价格后在线开箱，系统会根据预设的概率随机抽取箱子里的某一件物品。
        2. 盲盒对战。多人竞技：这是平台的一种高刺激度玩法。多名玩家（或玩家与机器人）同时选择加入同一个盲盒战局。胜者全拿：所有人开启相同的盲盒，最终抽中总价值最高的玩家将成为赢家，并拿走这一轮所有玩家抽中的全部物品；输掉的玩家则空手而归。
        3. 饰品/物品处置。用户抽到物品后，通常有两种处理方式：提取实物：如果抽到心仪的商品（如球星卡、手表），可以申请平台邮寄发货。回收/置换：如果抽到不喜欢的低价值“垃圾”物品，可以直接在平台内以一定比例折算成余额（账户代币），以便继续参与下一轮开箱。

        # ⚠️ 核心要求（必须严格遵守）

        ## 1. 覆盖率要求
        - **逐条对照**：需求文档中的每个功能点、每个业务规则都必须有对应测试点
        - **全覆盖清单**：功能测试 + 边界测试 + 异常测试 + 兼容性测试 + 用户体验测试 
        - **遗漏检查**：生成完成后自查是否遗漏需求中的任何功能

        ## 2. 去重要求（关键！）
        - **禁止重复**：相似含义的测试点合并为一个，不要用不同表达重复同一测试场景
        - **分类归纳**：同类测试场景归类到同一父节点下，避免分散
        - **精简表达**：每个测试点用一句话清晰表达，不啰嗦

        ## 3. 输出格式（严格遵循）
        ```
        # 模块名称 [P0/P1/P2]
        ## 功能点/页面名称
        ### 测试类型 > 测试场景 [P0/P1/P2]
        #### 具体测试点（可选项，用于细化）
        ```

        **测试类型标签**：
        - `[功能]` - 正常功能验证
        - `[边界]` - 边界值测试
        - `[异常]` - 异常/错误场景
        - `[UI]` - 界面视觉测试
        - `[UX]` - 用户体验测试
        - `[兼容]` - Android/iOS/H5/Web兼容

        ## 4. 优先级标注规则
        - **P0**：核心功能、阻断性bug、数据安全问题
        - **P1**：重要功能、常见场景、用户体验问题
        - **P2**：边缘场景、UI细节、非关键功能

        ## ⚠️ 禁止事项（严格遵守）
        - **禁止使用 BDD 词汇**：不要出现 Given、When、Then、given、when、then 等词汇
        - **禁止写测试步骤**：直接写测试点，不要写成"步骤1、步骤2"格式
        - **简洁直接**：每个测试点用一句话描述测试内容，例如"验证登录按钮点击后跳转正确"
        - **注意**:不要把其他不相关的需求加到这次需求中
        - **严禁**:严禁在每个二级节点下都增加兼容测试，必须只在一级节点下增加兼容测试！！！

        ---

        # 测试维度（每个功能点必须考虑以下维度）

        ## 功能测试
        - 正向流程：标准操作路径是否正确
        - 逆向流程：取消、返回、中断等操作
        - 边界值：数值上下限、字符长度极限、空值处理
        - 状态流转：各状态之间的转换逻辑
        - 数据一致性：前后端数据同步

        ## 异常测试
        - 操作异常：快速点击、重复提交、并发操作
        - 异常场景：不按正常流程来操作

        ## 兼容性测试
        - Android，iOS，H5，浏览器上的展示

        ---
        """

    def _system_prompt(self) -> str:
        """兼容接口"""
        return ""