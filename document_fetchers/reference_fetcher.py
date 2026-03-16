# reference_fetcher.py
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union, List
import re

from document_fetchers.local_fetcher import LocalDocumentFetcher


class XMindParser:
    """XMind 文件解析器 - 从.xmind提取文本内容"""

    NS_MAP = {
        'xmap': 'urn:xmind:xmap:xmlns:content:2.0',
        'svg': 'http://www.w3.org/2000/svg',
    }

    def parse(self, file_path: Union[str, Path]) -> str:
        """
        解析 XMind 文件，返回文本大纲
        """
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        # XMind 是 ZIP 格式
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                # 尝试读取 content.xml
                if 'content.xml' in zf.namelist():
                    content = zf.read('content.xml').decode('utf-8')
                    return self._parse_content_xml(content)
                elif 'content.json' in zf.namelist():
                    # XMind Zen 格式
                    import json
                    content = zf.read('content.json').decode('utf-8')
                    return self._parse_content_json(content)
                else:
                    raise ValueError("无法找到 content.xml 或 content.json")
        except zipfile.BadZipFile:
            raise ValueError("无效的 XMind 文件（非 ZIP 格式）")

    def _parse_content_xml(self, xml_content: str) -> str:
        """解析 XML 格式的 XMind"""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"XML 解析错误: {e}")

        # 找到所有 sheet
        sheets = root.findall('.//xmap:sheet', self.NS_MAP)
        if not sheets:
            # 尝试不带命名空间
            sheets = root.findall('.//sheet')

        all_text = []

        for sheet in sheets:
            sheet_title = self._get_title(sheet)
            if sheet_title:
                all_text.append(f"# {sheet_title}")

            # 找到根主题
            root_topic = sheet.find('.//xmap:topic', self.NS_MAP)
            if root_topic is None:
                root_topic = sheet.find('.//topic')

            if root_topic is not None:
                topic_text = self._extract_topic_tree(root_topic, level=0)
                if topic_text:
                    all_text.append(topic_text)

        return '\n'.join(all_text)

    def _parse_content_json(self, json_content: str) -> str:
        """解析 JSON 格式的 XMind (XMind Zen)"""
        import json
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析错误: {e}")

        all_text = []

        # 处理 rootTopic
        root_topic = data.get('rootTopic')
        if root_topic:
            topic_text = self._extract_json_topic(root_topic, level=0)
            if topic_text:
                all_text.append(topic_text)

        return '\n'.join(all_text)

    def _extract_topic_tree(self, topic_elem, level: int = 0) -> str:
        """递归提取 XML 主题树"""
        lines = []

        # 获取当前主题标题
        title = self._get_title(topic_elem)
        if title:
            indent = "  " * level
            prefix = "- " if level > 0 else "# "
            lines.append(f"{indent}{prefix}{title}")

        # 处理子主题
        children = topic_elem.find('.//xmap:children', self.NS_MAP)
        if children is None:
            children = topic_elem.find('.//children')

        if children is not None:
            # 获取 attached 类型的子主题
            topics = children.findall('.//xmap:topics', self.NS_MAP)
            if not topics:
                topics = children.findall('.//topics')

            for topics_group in topics:
                sub_topics = topics_group.findall('.//xmap:topic', self.NS_MAP)
                if not sub_topics:
                    sub_topics = topics_group.findall('.//topic')

                for sub_topic in sub_topics:
                    sub_text = self._extract_topic_tree(sub_topic, level + 1)
                    if sub_text:
                        lines.append(sub_text)

        return '\n'.join(lines)

    def _extract_json_topic(self, topic: dict, level: int = 0) -> str:
        """递归提取 JSON 主题树"""
        lines = []

        title = topic.get('title', '')
        if title:
            indent = "  " * level
            prefix = "- " if level > 0 else "# "
            lines.append(f"{indent}{prefix}{title}")

        # 处理子主题
        children = topic.get('children', {})
        attached = children.get('attached', [])

        for child in attached:
            child_text = self._extract_json_topic(child, level + 1)
            if child_text:
                lines.append(child_text)

        return '\n'.join(lines)

    def _get_title(self, elem) -> str:
        """获取元素的标题"""
        # 尝试命名空间版本
        title_elem = elem.find('.//xmap:title', self.NS_MAP)
        if title_elem is None:
            title_elem = elem.find('.//title')

        if title_elem is not None:
            # 获取文本内容
            text = ''.join(title_elem.itertext())
            return text.strip()
        return ""


class ReferenceFetcher(LocalDocumentFetcher):
    """
    历史测试点参考文档获取器
    专门用于读取用户上传的历史测试点，提取写作风格
    支持格式：.md .txt .docx .pdf .xmind
    """

    def __init__(self):
        super().__init__()
        self.xmind_parser = XMindParser()
        self.style_patterns = {
            'structure': [],  # 结构特征（如层级深度、编号方式）
            'terminology': set(),  # 术语偏好
            'test_types': [],  # 测试类型偏好
            'priority_marks': [],  # 优先级标记方式
        }

    def fetch(self, file_path: Union[str, Path]) -> str:
        """
        读取文档，支持 XMind 格式
        """
        path = Path(file_path).expanduser().resolve()

        # 检查是否是字符串内容
        if self._is_text_content(str(file_path)):
            return str(file_path)

        # 检查文件是否存在
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        # 检查是否是 XMind 文件
        if path.suffix.lower() == '.xmind':
            return self.xmind_parser.parse(path)

        # 其他格式使用父类方法
        return super().fetch(file_path)

    def fetch_reference_examples(self, sources: List[Union[str, Path]]) -> dict:
        """
        获取多个参考示例并分析风格
        :param sources: 文件路径列表或文本内容列表
        :return: 包含原始内容和风格分析的字典
        """
        examples = []

        for source in sources:
            try:
                # 判断是文件路径还是文本内容
                if self._is_text_content(str(source)):
                    content = str(source)
                else:
                    content = self.fetch(source)

                if content.strip():
                    examples.append({
                        'source': str(source)[:50],
                        'content': content,
                        'length': len(content)
                    })
            except Exception as e:
                print(f"警告：读取参考文档失败 ({source}): {e}")
                continue

        if not examples:
            return {'examples': [], 'style_guide': '', 'raw_contents': []}

        # 分析写作风格
        style_analysis = self._analyze_writing_style([ex['content'] for ex in examples])

        return {
            'examples': examples,
            'style_guide': self._generate_style_guide(style_analysis),
            'raw_contents': [ex['content'] for ex in examples]
        }

    def _analyze_writing_style(self, contents: List[str]) -> dict:
        """分析写作风格特征"""
        combined = '\n'.join(contents)

        analysis = {
            # 结构特征
            'max_depth': self._detect_hierarchy_depth(combined),
            'uses_numbering': bool(re.search(r'^\d+[\.\)]\s', combined, re.M)),
            'uses_bullets': '- ' in combined or '* ' in combined,

            # 测试点特征
            'has_priorities': bool(re.search(r'[Pp][0123]|【高|中|低】|【紧急|重要】', combined)),
            'has_test_types': bool(re.search(r'功能测试|性能测试|兼容性|边界测试|异常测试', combined)),
            'has_platform_tags': bool(re.search(r'安卓|iOS|Web|H5|小程序|Android', combined)),

            # 描述风格
            'avg_length': sum(len(c) for c in contents) // len(contents) if contents else 0,
            'uses_steps': '步骤' in combined or 'Step' in combined,
            'uses_given_when_then': bool(re.search(r'Given|When|Then|假如|当|那么', combined, re.I)),
        }

        return analysis

    def _detect_hierarchy_depth(self, content: str) -> int:
        """检测层级深度"""
        max_level = 0
        for line in content.split('\n'):
            level = 0
            stripped = line.lstrip()
            if stripped.startswith('#'):
                level = stripped.split()[0].count('#')
            elif stripped.startswith('-') or stripped.startswith('*'):
                indent = len(line) - len(stripped)
                level = 2 + (indent // 2)
            max_level = max(max_level, level)
        return max_level

    def _generate_style_guide(self, analysis: dict) -> str:
        """生成风格指导文本"""
        guide_parts = ["## 参考历史测试点的写作风格："]

        if analysis['uses_numbering']:
            guide_parts.append("- 使用数字编号（1. 2. 3.）组织测试点")
        if analysis['uses_bullets']:
            guide_parts.append("- 使用项目符号（- 或 *）列举细节")

        guide_parts.append(f"- 层级深度约 {analysis['max_depth']} 层")

        if analysis['has_priorities']:
            guide_parts.append("- 标注优先级（P0/P1/P2 或 高/中/低）")
        if analysis['has_test_types']:
            guide_parts.append("- 明确区分测试类型（功能/性能/兼容等）")
        if analysis['has_platform_tags']:
            guide_parts.append("- 标注适用平台（安卓/iOS/Web等）")
        if analysis['uses_steps']:
            guide_parts.append("- 包含测试步骤描述")
        if analysis['uses_given_when_then']:
            guide_parts.append("- 使用 Given/When/Then 格式描述场景")

        guide_parts.append(f"- 平均详细程度：{'详细' if analysis['avg_length'] > 5000 else '简洁'}")

        return '\n'.join(guide_parts)


def format_examples_for_prompt(examples_data: dict, max_chars: int = 8000) -> str:
    """
    将参考示例格式化为Prompt可用的字符串
    智能截断，保留最完整的示例
    """
    if not examples_data.get('examples'):
        return ""

    style_guide = examples_data.get('style_guide', '')
    contents = examples_data.get('raw_contents', [])

    if not contents:
        return style_guide

    # 按长度排序，优先保留完整的短示例
    contents.sort(key=len)

    formatted = [style_guide, "", "## 参考示例原文（请模仿其风格）：", ""]
    current_length = sum(len(s) for s in formatted)

    for i, content in enumerate(contents, 1):
        header = f"### 示例 {i}:"
        content_with_header = f"{header}\n{content}\n\n"

        if current_length + len(content_with_header) > max_chars:
            # 截断最后一个示例
            remaining = max_chars - current_length - len(header) - 50
            if remaining > 500:  # 至少保留500字符才有意义
                truncated = content[:remaining] + "\n... [内容截断]"
                formatted.append(f"{header}\n{truncated}\n\n")
            break

        formatted.append(content_with_header)
        current_length += len(content_with_header)

    return '\n'.join(formatted)