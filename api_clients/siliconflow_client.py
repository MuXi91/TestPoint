import requests
import json
from typing import Iterator


class SiliconFlowClient:
    """硅基流动客户端 - 修复403错误"""

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
        # 默认使用DeepSeek
        self.model = model or "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"

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
        return """# 角色定位
你是一位拥有10年+经验的资深软件测试专家，擅长测试用例设计、质量风险评估和测试策略制定。
你的任务是：基于提供的PRD/需求文档，生成一份结构清晰、覆盖全面、可直接落地的测试点文档。

# 项目背景
项目主要业务是开盲盒，用户充值后选择喜欢的盒子进行开盒，开盒结果是根据算法概率来的；
其次还有很多小业务例如对战，用户选择盒子后付款然后选择和机器人或者真人进行对战，那方胜利可以对方开出的所有的物品加上胜利方开出的物品，输方将不会获得任何物品。项目主要应用市场在海外。

# 测试维度要求（必须全部覆盖）

## 1. UI测试（界面视觉层）
- 布局验证：元素位置、对齐方式、间距符合设计稿等等
- 样式验证：字体、颜色、大小、圆角、阴影等视觉属性等等
- 响应式适配：不同分辨率/屏幕尺寸下的显示效果等等
- 图标/图片：清晰度、尺寸、加载状态、缺省图处理等等
- 交互动效：按钮点击反馈、页面转场、加载动画流畅度等等
- 暗黑模式/主题切换等等
- 英文文案显示等等

## 2. 功能测试（业务逻辑层）
- 正向流程：标准用户操作路径，验证核心功能可用等等
- 逆向流程：异常输入、非法操作、权限不足的容错处理等等
- 边界值：数值上下限、字符长度极限、空值/极值处理等等
- 等价类划分：有效/无效输入分类验证等等
- 状态流转：页面状态、数据状态的正确转换等等
- 数据一致性：前端展示与后端存储的同步验证等等
- 并发场景：多用户同时操作的冲突处理等等

## 3. 用户体验性测试（UX层）
- 操作路径：完成任务所需步骤是否最优等等
- 信息架构：导航层级是否清晰，找功能是否直观等等
- 反馈机制：操作成功/失败是否有明确提示等等
- 容错友好：错误提示是否易懂，是否提供解决方案等等
- 学习成本：新用户是否无需培训即可上手等等
- 无障碍访问：色盲友好、屏幕阅读器兼容等等
- 性能感知：操作响应是否跟手，有无卡顿感等等

## 4. 安全测试（防护层）
- 输入验证：SQL注入、XSS、命令注入防护
- 身份认证：登录态管理、Token过期、单点登录
- 权限控制：水平越权（访问他人数据）、垂直越权（访问高级功能）
- 敏感数据：加密存储、传输加密、日志脱敏
- 接口安全：防重放攻击、限流熔断、参数签名
- 文件上传：类型白名单、大小限制、病毒扫描（如支持）
- 敏感操作：二次确认、操作审计、异常行为监控

## 5. 性能测试（效率层）
- 加载性能：首屏时间、白屏时间、关键资源加载时长
- 渲染性能：FPS帧率、重绘重排频率、内存占用
- 交互性能：点击响应延迟、列表滚动流畅度、动画帧率
- 后端性能：接口响应时间（P50/P95/P99）、并发承载能力
- 稳定性：长时间运行是否内存泄漏、CPU占用是否持续攀升
- 弱网/离线：网络降级策略、离线缓存、超时重试机制
- 压力场景：大数据量列表、高频操作、极限并发下的表现

## 层级结构（严格遵循）
输出要求：
- 使用XMind兼容的Markdown格式
- 层级：#产品模块 -> ##功能点 -> ###测试场景
- 覆盖：功能测试、边界值测试、正常场景、异常场景、安卓兼容、web端兼容、iOS兼容、h5兼容、用户体验性、UI测试
- 每个测试点标注优先级（P0/P1/P2）"""

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