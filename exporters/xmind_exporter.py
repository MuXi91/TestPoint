import xmind
from xmind.core import workbook, saver
from xmind.core.topic import TopicElement
import re
from pathlib import Path
import zipfile
import os
import shutil


class XMindExporter:
    """XMind导出器 - 修复版"""

    def __init__(self):
        pass

    def export_from_markdown(self, markdown_content: str, output_path: str):
        """从Markdown生成XMind文件 - 使用稳定方法"""
        # 创建工作簿
        workbook = xmind.load("template.xmind")

        # 获取主画布
        sheet = workbook.getPrimarySheet()
        sheet.setTitle("测试点分析")

        # 获取根主题
        root_topic = sheet.getRootTopic()
        root_topic.setTitle("测试点")

        # 解析Markdown并构建树
        lines = markdown_content.split('\n')

        # 使用栈跟踪层级: [(level, topic_element), ...]
        topic_stack = [(0, root_topic)]

        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            # 计算层级
            level, title = self._parse_markdown_line(line)
            if level == 0 or not title:
                continue

            # 创建新主题
            new_topic = TopicElement()
            new_topic.setTitle(title)

            # 找到父主题（弹出高级别主题）
            while len(topic_stack) > 1 and topic_stack[-1][0] >= level:
                topic_stack.pop()

            # 添加到父主题
            parent_topic = topic_stack[-1][1]
            parent_topic.addSubTopic(new_topic)

            # 压入栈
            topic_stack.append((level, new_topic))

        # 保存 - 使用多种方法尝试
        self._safe_save(workbook, output_path)

        return output_path

    def _parse_markdown_line(self, line: str) -> tuple:
        """解析Markdown行，返回(层级, 标题)"""
        stripped = line.lstrip()

        # 标题
        if stripped.startswith('# '):
            return (1, stripped[2:].strip())
        elif stripped.startswith('## '):
            return (2, stripped[3:].strip())
        elif stripped.startswith('### '):
            return (3, stripped[4:].strip())
        elif stripped.startswith('#### '):
            return (4, stripped[5:].strip())
        elif stripped.startswith('##### '):
            return (5, stripped[6:].strip())

        # 列表项
        elif stripped.startswith('- ') or stripped.startswith('* '):
            return (6, stripped[2:].strip())
        elif re.match(r'^\d+\.\s', stripped):
            return (6, re.sub(r'^\d+\.\s', '', stripped).strip())

        # 普通文本（跳过）
        return (0, "")

    def _safe_save(self, workbook, output_path: str):
        """安全保存，尝试多种方法"""
        errors = []

        # 方法1: 标准saver
        try:
            saver.save(workbook, output_path)
            return
        except Exception as e:
            errors.append(f"saver.save: {e}")

        # 方法2: workbook.save
        try:
            workbook.save(output_path)
            return
        except Exception as e:
            errors.append(f"workbook.save: {e}")

        # 方法3: 手动构建XMind文件（ZIP格式）
        try:
            self._manual_save(workbook, output_path)
            return
        except Exception as e:
            errors.append(f"manual_save: {e}")

        # 都失败了
        raise Exception(f"所有保存方法均失败:\n" + "\n".join(errors))

    def _manual_save(self, workbook, output_path: str):
        """手动构建XMind文件"""
        import xml.dom.minidom as minidom

        # 创建工作簿DOM
        impl = minidom.getDOMImplementation()
        doc = impl.createDocument(None, "xmap-content", None)

        # 获取原始workbook的XML内容
        try:
            # 尝试序列化workbook
            content_xml = self._serialize_workbook(workbook)
        except:
            # 手动构建基本结构
            content_xml = self._build_basic_xmind(workbook)

        # 创建临时目录
        temp_dir = Path(output_path).parent / ".xmind_temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 写入content.xml
            content_path = temp_dir / "content.xml"
            with open(content_path, 'w', encoding='utf-8') as f:
                f.write(content_xml)

            # 创建meta.xml
            meta_path = temp_dir / "meta.xml"
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<meta version="2.0" xmlns="urn:xmind:xmap:xmlns:meta:2.0"/>
""")

            # 创建manifest.json
            manifest_path = temp_dir / "META-INF" / "manifest.xml"
            manifest_path.parent.mkdir(exist_ok=True)
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
<file-entry full-path="content.xml" media-type="text/xml"/>
<file-entry full-path="meta.xml" media-type="text/xml"/>
</manifest>
""")

            # 打包为ZIP（XMind格式）
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(content_path, "content.xml")
                zf.write(meta_path, "meta.xml")
                zf.write(manifest_path, "META-INF/manifest.xml")

        finally:
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _serialize_workbook(self, workbook) -> str:
        """序列化workbook为XML"""
        # 尝试获取内部DOM
        try:
            # 访问workbook的document
            if hasattr(workbook, 'getOwnerDocument'):
                doc = workbook.getOwnerDocument()
                return doc.toxml(encoding='utf-8')
        except:
            pass

        # 备用：手动序列化
        return self._build_basic_xmind(workbook)

    def _build_basic_xmind(self, workbook) -> str:
        """手动构建基本XMind XML"""
        sheet = workbook.getPrimarySheet()
        root = sheet.getRootTopic()

        def build_topic_xml(topic, indent=2):
            title = topic.getTitle() or ""
            # XML转义
            title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

            xml = ' ' * indent + f'<topic id="{id(topic)}">\n'
            xml += ' ' * (indent + 2) + f'<title>{title}</title>\n'

            # 子主题
            children = []
            try:
                children = topic.getSubTopics() or []
            except:
                pass

            if children:
                xml += ' ' * (indent + 2) + '<children>\n'
                xml += ' ' * (indent + 4) + '<topics type="attached">\n'
                for child in children:
                    xml += build_topic_xml(child, indent + 6)
                xml += ' ' * (indent + 4) + '</topics>\n'
                xml += ' ' * (indent + 2) + '</children>\n'

            xml += ' ' * indent + '</topic>\n'
            return xml

        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<xmap-content version="2.0" xmlns="urn:xmind:xmap:xmlns:content:2.0">
  <sheet id="1" timestamp="''' + str(int(time.time())) + '''">
    <topic id="root" structure-class="org.xmind.ui.logic.right">
'''
        xml += build_topic_xml(root, 6)
        xml += '''    </topic>
  </sheet>
</xmap-content>
'''
        return xml


import time