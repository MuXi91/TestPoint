# test_generator.py
from typing import Iterator, Optional, List
from core.analyzer import RequirementAnalyzer
from document_fetchers.local_fetcher import LocalDocumentFetcher
from document_fetchers.lanhu_fetcher import LanhuFetcher
from document_fetchers.reference_fetcher import ReferenceFetcher, format_examples_for_prompt  # 新增


class TestPointGenerator:
    def __init__(self, ai_client, analyzer: Optional[RequirementAnalyzer] = None):
        self.ai_client = ai_client
        self.analyzer = analyzer or RequirementAnalyzer()
        self.req_fetcher = LocalDocumentFetcher()
        self.prd_fetcher = LanhuFetcher()
        self.reference_fetcher = ReferenceFetcher()  # 新增
        self.reference_examples = None  # 缓存参考示例

    def set_reference_examples(self, reference_sources: List[str]):
        """设置历史测试点参考"""
        if reference_sources:
            self.reference_examples = self.reference_fetcher.fetch_reference_examples(reference_sources)

    def generate(self, requirement: str, prd: str, stream: bool = True) -> Iterator[str]:
        """生成测试点"""
        # 1. 获取文档内容
        self._emit_progress("正在读取需求文档...")
        req_content = self._get_requirement_content(requirement)

        self._emit_progress("正在读取PRD文档...")
        prd_content = self._get_prd_content(prd)

        # 2. 预分析
        self._emit_progress("正在分析文档结构...")
        analysis = self.analyzer.analyze(req_content, prd_content)

        # 3. 构建增强提示
        enhanced_prompt = self._build_enhanced_prompt(req_content, prd_content, analysis)

        # 4. 调用AI生成
        self._emit_progress("正在生成测试点...")
        if stream:
            yield from self.ai_client.generate_test_points(enhanced_prompt, "")
        else:
            result = "".join(self.ai_client.generate_test_points(enhanced_prompt, ""))
            yield result

    def _emit_progress(self, message: str):
        """发送进度消息（供子类重写或使用回调）"""
        print(message)  # 默认打印，GUI中会覆盖

    def _get_requirement_content(self, source: str) -> str:
        """获取需求文档内容（支持多文件或纯文本）"""
        source = source.strip()
        if not source:
            return ""

        # 判断是文件路径还是纯文本
        if self.req_fetcher._is_text_content(source):
            return source

        try:
            # 支持多文件（分号分隔）
            return self.req_fetcher.fetch_and_merge(source)
        except Exception as e:
            print(f"警告：读取需求文档失败({e})，作为纯文本处理")
            return source

    def _get_prd_content(self, source: str) -> str:
        """获取PRD内容（蓝湖URL、本地文件或纯文本）"""
        source = source.strip()
        if not source:
            return ""

        # 使用蓝湖获取器（自动判断类型）
        try:
            return self.prd_fetcher.fetch(source)
        except Exception as e:
            print(f"警告：读取PRD失败({e})，作为纯文本处理")
            return source

    def _build_enhanced_prompt(self, req: str, prd: str, analysis: dict) -> str:
        """构建增强提示 - 加入风格参考"""
        context_parts = []

        # 1. 预分析结果
        context_parts.append(f"""
【文档分析结果】
- 功能模块数量：{len(analysis.get('modules', []))} 个
- 用户故事数量：{len(analysis.get('user_stories', []))} 个
- 业务规则数量：{len(analysis.get('business_rules', []))} 条
- UI组件数量：{len(analysis.get('ui_components', []))} 个
- 数据流程数量：{len(analysis.get('data_flows', []))} 个
- 风险提醒：{', '.join(analysis.get('risk_areas', [])) or '无'}
""")

        # 2. 模块列表（帮助模型逐个覆盖）
        if analysis.get('modules'):
            modules_str = '\n'.join([f"  - {m}" for m in analysis['modules'][:20]])
            context_parts.append(f"\n【识别到的功能模块】\n{modules_str}\n")

        # 3. 业务规则列表
        if analysis.get('business_rules'):
            rules_str = '\n'.join([f"  - {r}" for r in analysis['business_rules'][:15]])
            context_parts.append(f"\n【业务规则】\n{rules_str}\n")

        # 4. 风格参考（新增）
        if self.reference_examples:
            style_section = format_examples_for_prompt(self.reference_examples, max_chars=6000)
            context_parts.append(
                f"\n\n{style_section}\n\n【重要】生成要求：严格模仿上述示例的写作风格、层级结构、术语使用和标注习惯。")

        context = '\n'.join(context_parts)

        return f"{context}\n\n需求文档：\n{req}\n\nPRD文档：\n{prd}"