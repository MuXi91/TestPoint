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
- **全覆盖清单**：功能测试 + 边界测试 + 异常测试 + 兼容性测试 + UI测试 + 用户体验测试 + 安全测试 + 性能测试
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
#### 具体测试点（需要对功能点拆分细化）
```

**测试类型标签**：
- `[功能]` - 正常功能验证
- `[边界]` - 边界值测试
- `[异常]` - 异常/错误场景
- `[UI]` - 界面视觉测试
- `[UX]` - 用户体验测试
- `[兼容]` - Android/iOS/H5/Web兼容
- `[安全]` - 安全性测试
- `[性能]` - 性能相关测试

## 4. 优先级标注规则
- **P0**：核心功能、阻断性bug、数据安全问题
- **P1**：重要功能、常见场景、用户体验问题
- **P2**：边缘场景、UI细节、非关键功能

## ⚠️ 禁止事项（严格遵守）
- **禁止使用 BDD 词汇**：不要出现 Given、When、Then、given、when、then 等词汇
- **禁止写测试步骤**：直接写测试点，不要写成"步骤1、步骤2"格式
- **简洁直接**：每个测试点用一句话描述测试内容，例如"验证登录按钮点击后跳转正确"
- **异常测试点**：异常测试点需要考虑场景周全，不能漏掉，例如：触发条件是需要开过注册免费盒，那正常流程就是开完注册免费盒，异常流程就是没有开注册免费盒是否会触发

---

# 测试维度（每个功能点必须考虑以下维度）

## 功能测试
- 正向流程：标准操作路径是否正确
- 逆向流程：取消、返回、中断等操作
- 边界值：数值上下限、字符长度极限、空值处理
- 状态流转：各状态之间的转换逻辑
- 数据一致性：前后端数据同步
- 场景法：正常场景，异常场景

## 异常测试
- 网络异常：断网、弱网、超时
- 数据异常：空数据、超长数据、特殊字符
- 操作异常：快速点击、重复提交、并发操作

## 兼容性测试
- Android：不同版本、不同品牌、不同分辨率
- iOS：不同版本、不同机型
- H5：不同浏览器
- 多端同步：同一账号多设备登录

## UI/UX测试
- 布局样式：符合设计稿
- 交互反馈：加载状态、成功/失败提示
- 文案显示：英文文案正确、无截断

## 安全测试
- 输入验证：注入防护
- 权限控制：越权访问
- 敏感数据：加密存储传输

## 性能测试
- 响应时间：接口响应、页面加载
- 稳定性：内存泄漏、崩溃

---

# 输出检查清单（生成后自查）
1. ✅ 需求文档每个功能点都有覆盖？
2. ✅ 没有重复或相似的测试点？
3. ✅ 每个测试点都标注了优先级？
4. ✅ 每个测试点都标注了测试类型？
5. ✅ 边界值和异常场景都考虑了？"""

    def _build_prompt(self, requirement: str, prd: str) -> str:
        return f"""请基于以下需求文档和PRD生成完整的测试点。

---

## 需求文档：
{requirement[:30000]}

---

## PRD文档：
{prd[:30000]}

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
3. [异常] 异常场景（必须齐全）
4. [兼容] 多端兼容
5. [UI] 界面验证
6. [安全] 安全检查

### 步骤3：去重检查
- 合并含义相同的测试点
- 删除重复表达的测试点
- 确保每个测试点都有独特价值

### 步骤4：格式输出
按 Markdown 层级格式输出，便于导入 XMind。

现在开始生成测试点："""