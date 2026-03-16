import re
import json
import time
import sys
import warnings
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

import fitz
import requests


@dataclass
class PDFPageContent:
    """PDF页面内容结构"""
    page_number: int
    text: str
    has_images: bool
    layout_type: str


class LanhuFetcher:
    """
    蓝湖PRD获取器 - 终极增强版
    专门针对蓝湖导出的PDF优化（图片+文字混合）
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        # 忽略警告
        warnings.filterwarnings("ignore")

    def fetch(self, source: str) -> str:
        """获取PRD内容"""
        source = source.strip()
        if not source:
            return ""

        # 判断输入类型
        if self._is_lanhu_url(source):
            return self._fetch_from_url(source)
        elif self._is_local_file(source):
            return self._read_local_file(source)
        else:
            # 纯文本直接返回
            return source

    def _is_lanhu_url(self, text: str) -> bool:
        """判断是否是蓝湖URL"""
        patterns = [r'lanhuapp\.com', r'lanhu\.com', r'/url/', r'/web/#/item/']
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _is_local_file(self, text: str) -> bool:
        """判断是否是本地文件路径"""
        if text.startswith(('/', './', '../', '~/', 'C:\\', 'D:\\', 'E:\\')):
            return True
        if Path(text).expanduser().exists():
            return True
        if any(ext in text.lower() for ext in ['.md', '.txt', '.docx', '.pdf']):
            if not text.startswith('http'):
                return True
        return False

    # ==================== 本地文件读取 ====================

    def _read_local_file(self, file_path: str) -> str:
        """读取本地文件"""
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        ext = path.suffix.lower()

        if ext == '.pdf':
            return self._read_pdf_comprehensive(path)
        elif ext in ['.md', '.txt', '.html']:
            return self._read_text_file(path)
        elif ext == '.docx':
            return self._read_docx(path)
        else:
            return self._read_text_file(path)

    def _read_pdf_comprehensive(self, pdf_path: Path) -> str:
        """
        综合PDF读取策略 - 针对蓝湖PDF优化
        蓝湖PDF特点：图片为主，文字可能在图片上或独立文本层
        """
        print(f"正在读取PDF: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")

        results = []

        # 策略1: pdfplumber（提取文本层和表格）
        try:
            print("  尝试 pdfplumber...")
            text = self._read_with_pdfplumber(pdf_path)
            if len(text) > 200:
                results.append(("pdfplumber", text, len(text)))
                print(f"    ✓ 提取 {len(text)} 字符")
        except Exception as e:
            print(f"    ✗ 失败: {e}")

        # 策略2: PyMuPDF（更好的文字定位和OCR预备）
        try:
            print("  尝试 PyMuPDF...")
            text = self._read_with_pymupdf_advanced(pdf_path)
            if len(text) > 200:
                results.append(("pymupdf", text, len(text)))
                print(f"    ✓ 提取 {len(text)} 字符")
        except Exception as e:
            print(f"    ✗ 失败: {e}")

        # 策略3: OCR（如果上面都失败或内容太少，说明是图片PDF）
        if not results or max(r[2] for r in results) < 500:
            try:
                print("  尝试 OCR识别...")
                text = self._read_with_ocr(pdf_path)
                if len(text) > 100:
                    results.append(("ocr", text, len(text)))
                    print(f"    ✓ OCR识别 {len(text)} 字符")
            except Exception as e:
                print(f"    ✗ OCR失败: {e}")

        # 策略4: 转换为图片后OCR（最后手段）
        if not results:
            try:
                print("  尝试 PDF转图片+OCR...")
                text = self._pdf_to_images_ocr(pdf_path)
                if len(text) > 100:
                    results.append(("pdf2image+ocr", text, len(text)))
                    print(f"    ✓ 识别 {len(text)} 字符")
            except Exception as e:
                print(f"    ✗ 失败: {e}")

        # 选择最佳结果或合并
        if not results:
            return self._create_error_content(pdf_path, "无法提取PDF内容，可能是扫描件或加密PDF")

        # 选择最长的结果
        best = max(results, key=lambda x: x[2])
        print(f"  最佳结果: {best[0]} ({best[2]} 字符)")

        # 后处理优化
        optimized = self._optimize_content(best[1], pdf_path.name)
        return optimized

    def _read_with_pdfplumber(self, pdf_path: Path) -> str:
        """使用pdfplumber读取PDF"""
        import pdfplumber

        all_texts = []

        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                page_text = f"\n=== 第{i}页 ===\n"

                # 提取表格
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            table_text = self._format_table(table)
                            if table_text:
                                page_text += f"\n【表格】\n{table_text}\n"
                except:
                    pass

                # 提取文本（多种策略）
                text = ""

                # 策略A: 标准提取
                try:
                    text = page.extract_text() or ""
                except:
                    pass

                # 策略B: layout模式
                if len(text) < 50:
                    try:
                        text = page.extract_text(layout=True) or ""
                    except:
                        pass

                # 策略C: 宽松模式
                if len(text) < 50:
                    try:
                        text = page.extract_text(x_tolerance=5, y_tolerance=5) or ""
                    except:
                        pass

                # 策略D: 字符级提取（处理字体问题）
                if len(text) < 20:
                    try:
                        chars = page.chars
                        if chars:
                            # 按位置分组
                            lines = {}
                            for char in chars:
                                y = round(char['top'] / 15) * 15  # 行分组
                                if y not in lines:
                                    lines[y] = []
                                lines[y].append((char['x0'], char['text']))

                            sorted_lines = []
                            for y in sorted(lines.keys()):
                                chars_sorted = sorted(lines[y], key=lambda x: x[0])
                                line_text = ''.join(c[1] for c in chars_sorted)
                                sorted_lines.append(line_text)

                            text = '\n'.join(sorted_lines)
                    except Exception as e:
                        print(f"      字符提取失败: {e}")

                if text.strip():
                    page_text += text.strip()

                # 检测图片
                try:
                    if page.images:
                        page_text += f"\n[本页包含 {len(page.images)} 个图片/原型图]"
                except:
                    pass

                all_texts.append(page_text)

        return '\n\n'.join(all_texts)

    def _read_with_pymupdf_advanced(self, pdf_path: Path) -> str:
        """使用PyMuPDF高级读取"""
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        all_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = f"\n=== 第{page_num + 1}页 ===\n"

            # 提取带格式的文本块
            blocks = page.get_text("dict")["blocks"]

            # 按垂直位置排序
            blocks.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

            text_parts = []
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")

                        # 根据字体大小判断重要性
                        if line.get("spans"):
                            size = line["spans"][0].get("size", 12)
                            flags = line["spans"][0].get("flags", 0)

                            # 粗体或大字可能是标题
                            if size > 14 or flags & 2 ** 4:  # 粗体标志
                                line_text = f"【{line_text}】"

                        if line_text.strip():
                            text_parts.append(line_text)

            if text_parts:
                page_text += '\n'.join(text_parts)

            # 检测图形和图片
            images = page.get_images()
            drawings = page.get_drawings()

            if images or drawings:
                page_text += f"\n[包含 {len(images)} 图片, {len(drawings)} 图形元素]"

            # 尝试OCR识别图片上的文字（如果安装了paddleocr）
            if len(text_parts) < 5 and (images or drawings):
                try:
                    ocr_text = self._ocr_page_with_paddle(page)
                    if ocr_text:
                        page_text += f"\n【图片文字识别】\n{ocr_text}"
                except:
                    pass

            all_pages.append(page_text)

        doc.close()
        return '\n\n'.join(all_pages)

    def _read_with_ocr(self, pdf_path: Path) -> str:
        """使用OCR读取PDF（针对图片型PDF）"""
        # 尝试多种OCR方案

        # 方案1: pdf2image + pytesseract
        try:
            return self._ocr_with_tesseract(pdf_path)
        except Exception as e:
            print(f"    Tesseract OCR失败: {e}")

        # 方案2: paddleocr（如果安装）
        try:
            return self._ocr_with_paddle(pdf_path)
        except Exception as e:
            print(f"    PaddleOCR失败: {e}")

        # 方案3: easyocr
        try:
            return self._ocr_with_easyocr(pdf_path)
        except Exception as e:
            print(f"    EasyOCR失败: {e}")

        raise Exception("所有OCR方案均失败")

    def _ocr_with_tesseract(self, pdf_path: Path) -> str:
        """使用Tesseract OCR"""
        from pdf2image import convert_from_path
        import pytesseract

        print("    使用Tesseract OCR...")

        # 转换PDF为图片
        images = convert_from_path(str(pdf_path), dpi=200)

        all_text = []
        for i, image in enumerate(images, 1):
            print(f"      识别第{i}/{len(images)}页...")
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            if text.strip():
                all_text.append(f"\n=== 第{i}页 ===\n{text.strip()}")

        return '\n\n'.join(all_text)

    def _ocr_with_paddle(self, pdf_path: Path) -> str:
        """使用PaddleOCR（中文识别效果好）"""
        from pdf2image import convert_from_path
        from paddleocr import PaddleOCR

        print("    使用PaddleOCR...")

        ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

        images = convert_from_path(str(pdf_path), dpi=200)

        all_text = []
        for i, image in enumerate(images, 1):
            print(f"      识别第{i}/{len(images)}页...")

            # 临时保存图片
            temp_path = f"/tmp/ocr_temp_{i}.png"
            image.save(temp_path)

            result = ocr.ocr(temp_path, cls=True)

            if result and result[0]:
                texts = [line[1][0] for line in result[0]]
                page_text = '\n'.join(texts)
                all_text.append(f"\n=== 第{i}页 ===\n{page_text}")

            Path(temp_path).unlink(missing_ok=True)

        return '\n\n'.join(all_text)

    def _ocr_with_easyocr(self, pdf_path: Path) -> str:
        """使用EasyOCR"""
        from pdf2image import convert_from_path
        import easyocr

        print("    使用EasyOCR...")

        reader = easyocr.Reader(['ch_sim', 'en'])

        images = convert_from_path(str(pdf_path), dpi=200)

        all_text = []
        for i, image in enumerate(images, 1):
            print(f"      识别第{i}/{len(images)}页...")

            temp_path = f"/tmp/ocr_temp_{i}.png"
            image.save(temp_path)

            result = reader.readtext(temp_path, detail=0)
            if result:
                page_text = '\n'.join(result)
                all_text.append(f"\n=== 第{i}页 ===\n{page_text}")

            Path(temp_path).unlink(missing_ok=True)

        return '\n\n'.join(all_text)

    def _ocr_page_with_paddle(self, page) -> str:
        """对单页进行OCR（PyMuPDF页面）"""
        from paddleocr import PaddleOCR
        import numpy as np

        ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

        # 渲染页面为图片
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x缩放提高清晰度
        img_data = pix.tobytes("png")

        # 保存临时文件
        temp_path = "/tmp/temp_ocr_page.png"
        with open(temp_path, "wb") as f:
            f.write(img_data)

        result = ocr.ocr(temp_path, cls=True)

        Path(temp_path).unlink(missing_ok=True)

        if result and result[0]:
            return '\n'.join([line[1][0] for line in result[0]])

        return ""

    def _pdf_to_images_ocr(self, pdf_path: Path) -> str:
        """PDF转图片后OCR（备用方案）"""
        # 使用系统命令转换
        output_dir = Path("/tmp/pdf_images")
        output_dir.mkdir(exist_ok=True)

        try:
            # 使用pdftoppm或convert
            result = subprocess.run([
                "pdftoppm", "-png", "-r", "200",
                str(pdf_path), str(output_dir / "page")
            ], capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                # 尝试ImageMagick
                result = subprocess.run([
                    "convert", "-density", "200",
                    str(pdf_path), str(output_dir / "page-%03d.png")
                ], capture_output=True, text=True, timeout=120)

            # 对生成的图片OCR
            images = sorted(output_dir.glob("*.png"))

            if not images:
                raise Exception("PDF转图片失败")

            # 使用Tesseract批量识别
            all_text = []
            for i, img_path in enumerate(images, 1):
                result = subprocess.run(
                    ["tesseract", str(img_path), "stdout", "-l", "chi_sim+eng"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    all_text.append(f"\n=== 第{i}页 ===\n{result.stdout.strip()}")

            # 清理
            for img in images:
                img.unlink()

            return '\n\n'.join(all_text)

        except Exception as e:
            raise Exception(f"PDF转图片OCR失败: {e}")

    # ==================== 工具方法 ====================

    def _format_table(self, table: List[List]) -> str:
        """格式化表格"""
        if not table:
            return ""

        # 清理
        cleaned = []
        for row in table:
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            if any(cleaned_row):
                cleaned.append(cleaned_row)

        if not cleaned:
            return ""

        # Markdown表格
        max_cols = max(len(row) for row in cleaned)

        lines = []
        header = cleaned[0] + [""] * (max_cols - len(cleaned[0]))
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        for row in cleaned[1:]:
            row = row + [""] * (max_cols - len(row))
            lines.append("| " + " | ".join(row[:max_cols]) + " |")

        return '\n'.join(lines)

    def _optimize_content(self, content: str, filename: str) -> str:
        """优化内容结构"""
        # 清理
        content = re.sub(r'\n{5,}', '\n\n\n', content)

        # 添加元信息头
        header = f"""# PRD文档: {filename}

> 解析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
> 原始格式: PDF（蓝湖导出）
> 内容长度: {len(content)} 字符
> 注意: 蓝湖PDF可能包含大量原型图，文字识别可能不完整，建议对照原始设计稿核对

---

"""

        return header + content

    def _create_error_content(self, pdf_path: Path, error_msg: str) -> str:
        """创建错误提示内容"""
        return f"""# PRD读取失败

## 错误信息
{error_msg}

## 文件信息
- 路径: {pdf_path}
- 大小: {pdf_path.stat().st_size / 1024:.1f} KB

# ## 建议解决方案
# 
# ### 方案1: 使用蓝湖"导出Word"功能（推荐）
# 1. 在蓝湖页面点击「导出」→「导出Word」
# 2. 保存.docx文件
# 3. 使用本工具选择该文件
# 
# ### 方案2: 复制粘贴文本
# 1. 在蓝湖页面选中PRD文本
# 2. 复制粘贴到工具的文本框
# 
# ### 方案3: 安装OCR依赖（自动识别图片文字）
# ```bash
# pip install pdf2image pytesseract paddleocr easyocr
# # macOS额外需要:
# brew install tesseract tesseract-lang
# brew install poppler  # for pdf2image """