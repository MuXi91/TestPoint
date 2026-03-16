from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
import re


class MarkdownExporter:
    """导出为XMind兼容的Markdown格式和OPML"""

    def export(self, content: str, output_path: str = None) -> str:
        """导出为Markdown"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"test_points_{timestamp}.md"

        # 优化为XMind导入友好的格式
        optimized = self._optimize_for_xmind(content)

        Path(output_path).write_text(optimized, encoding='utf-8')
        return output_path

    def _optimize_for_xmind(self, content: str) -> str:
        """优化为XMind可识别的Markdown结构"""
        lines = content.split('\n')
        result = []

        # XMind导入需要的特定格式
        result.append("# 测试点分析")
        result.append("")
        result.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        result.append("")
        result.append("---")
        result.append("")

        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            # 确保层级正确
            if line.startswith('#') and not line.startswith('# '):
                # 修复多级标题格式
                if not line.startswith('## ') and not line.startswith('### '):
                    line = line.replace('#', '# ', 1)

            result.append(line)

        return '\n'.join(result)

    def export_opml(self, content: str, output_path: str) -> str:
        """
        导出为OPML格式（XMind原生支持）
        比.xmind更稳定可靠
        """
        # 创建OPML结构
        root = ET.Element('opml', version='2.0')

        # Head
        head = ET.SubElement(root, 'head')
        title = ET.SubElement(head, 'title')
        title.text = "测试点分析"

        # Body
        body = ET.SubElement(root, 'body')

        # 解析内容构建大纲
        lines = content.split('\n')

        # 栈: (level, outline_element)
        stack = [(0, body)]

        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            level, text = self._parse_line(line)
            if level == 0 or not text:
                continue

            # 创建outline元素
            outline = ET.Element('outline', text=text)

            # 找到正确的父元素
            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                stack[-1][1].append(outline)

            # 将自己压入栈
            stack.append((level, outline))

        # 保存
        tree = ET.ElementTree(root)

        # 注册命名空间（避免ns0前缀）
        ET.register_namespace('', '')

        # 格式化写入
        self._indent(root)  # 美化缩进

        tree.write(output_path, encoding='utf-8', xml_declaration=True)

        return output_path

    def _parse_line(self, line: str) -> tuple:
        """解析行层级"""
        stripped = line.lstrip()

        # 标题层级
        if stripped.startswith('# '):
            return (1, stripped[2:])
        elif stripped.startswith('## '):
            return (2, stripped[3:])
        elif stripped.startswith('### '):
            return (3, stripped[4:])
        elif stripped.startswith('#### '):
            return (4, stripped[5:])
        elif stripped.startswith('##### '):
            return (5, stripped[6:])

        # 列表项
        elif stripped.startswith('- ') or stripped.startswith('* '):
            return (6, stripped[2:])
        elif re.match(r'^\d+\.\s', stripped):
            return (6, re.sub(r'^\d+\.\s', '', stripped))

        # 普通文本（作为叶子节点）
        if stripped and not stripped.startswith('---') and not stripped.startswith('>'):
            # 如果前面有空格，可能是缩进列表
            indent = len(line) - len(stripped)
            if indent >= 4:
                return (7, stripped)
            return (6, stripped)

        return (0, "")

    def _indent(self, elem, level=0):
        """美化XML缩进"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i


# 别名保持兼容
export_xmind_opml = MarkdownExporter().export_opml