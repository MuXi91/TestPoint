import requests
import json
from typing import Iterator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# 禁用SSL警告（仅用于解决特定SSL连接问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiliconFlowClient:
    """硅基流动客户端 - 修复403错误和SSL连接问题"""

    API_BASE = "https://api.siliconflow.cn/v1"

    # 确认可用的免费模型（2024年3月测试通过）
    AVAILABLE_MODELS = {
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B":"DeepSeek-R1-Distill-Qwen-32B",
        # Tier 1: 高额度，推荐
        "Qwen/Qwen2.5-72B-Instruct": "通义千问2.5-72B（推荐）",
        "Qwen/Qwen2.5-32B-Instruct": "通义千问2.5-32B",
        "Qwen/Qwen2.5-14B-Instruct": "通义千问2.5-14B",

        # Tier 2: 其他免费模型
        "THUDM/GLM-Z1-32B-0414": "智谱GLM-Z1-32B-0414",
        "01-ai/Yi-1.5-34B-Chat": "零一万物Yi-1.5-34B",
        "internlm/internlm2_5-20b-chat": "书生浦语2.5-20B",
        "internlm/internlm2_5-7b-chat": "书生浦语2.5-7B",
    }

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key.strip()
        # 默认使用Qwen2.5-72B（推理能力最强）
        self.model = model or "Qwen/Qwen2.5-72B-Instruct"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 创建带有重试策略的 session，解决 SSL 连接问题
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

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
            "max_tokens": 8192,
            "temperature": 0.1,
            "top_p": 0.85,
            "presence_penalty": 0.3,
            "frequency_penalty": 0.3,
        }

        try:
            response = self.session.post(
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
        return """# 角色定位
你是一位拥有10年+经验的资深软件测试专家，擅长测试用例设计、质量风险评估和测试策略制定。
你的任务是：基于提供的PRD/需求文档，生成一份结构清晰、覆盖全面、可直接落地的测试点文档。

# 项目背景
项目主要业务是开盲盒，用户充值后选择喜欢的盒子进行开盒，开盒结果是根据算法概率来的；
其次还有很多小业务例如对战，用户选择盒子后付款然后选择和机器人或者真人进行对战，那方胜利可以对方开出的所有的物品加上胜利方开出的物品，输方将不会获得任何物品。项目主要应用市场在海外。

# ⚠️ 核心要求（必须严格遵守）

## 1. 覆盖率要求
- **逐条对照**：需求文档中的每个功能点、每个业务规则都必须有对应测试点
- **全覆盖清单**：功能测试 + 边界测试 + 异常测试 + 兼容性测试 + UI测试 + 用户体验测试 
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
- 网络异常：断网、弱网、超时
- 数据异常：空数据、超长数据、特殊字符
- 操作异常：快速点击、重复提交、并发操作

## 兼容性测试
- Android，iOS，H5，浏览器上的展示


## UI/UX测试
- 布局样式：符合设计稿
- 交互反馈：加载状态、成功/失败提示
- 文案显示：英文文案正确、无截断

---
"""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        req = requirement[:20000] if len(requirement) > 20000 else requirement
        prd_text = prd[:20000] if len(prd) > 20000 else prd
        return f"""请基于以下需求文档和PRD生成完整的测试点。

---

## 需求文档：
{req}

---

## PRD文档：
{prd_text}

---

## 生成要求：

### 步骤1：功能点提取
先提取需求文档中的所有功能点，确保不遗漏：
- 核心业务功能
- 辅助功能
- 数据处理逻辑
- 权限控制

### 步骤2：逐个功能点生成测试点
对每个功能点，按以下维度生成测试点：
1. [功能] 正常流程
2. [边界] 边界值测试
3. [异常] 异常场景
4. [兼容] Android，iOS，H5，浏览器上的展示
5. [UI] 界面验证

### 步骤3：去重检查
- 合并含义相同的测试点
- 删除重复表达的测试点
- 确保每个测试点都有独特价值

### 步骤4：格式输出
按 Markdown 层级格式输出，便于导入 XMind。

现在开始生成测试点："""

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
            resp = self.session.post(
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