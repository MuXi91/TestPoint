import sys
import threading
import webbrowser
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QFileDialog, QMessageBox, QProgressBar, QGroupBox,
    QSplitter, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette

from config import Config
from core.test_generator import TestPointGenerator
from core.analyzer import RequirementAnalyzer
from document_fetchers.reference_fetcher import ReferenceFetcher
from exporters.xmind_exporter import XMindExporter
from exporters.markdown_exporter import MarkdownExporter
from document_fetchers.local_fetcher import LocalDocumentFetcher


# ============ 工作线程类 ============

class GenerationWorker(QThread):
    """测试点生成工作线程"""
    # 将信号定义为类属性，避免线程安全问题
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, generator: TestPointGenerator, req_source: str, prd_source: str):
        super().__init__()
        self.generator = generator
        self.req_source = req_source
        self.prd_source = prd_source
        self._is_running = True

    def run(self):
        """执行生成任务"""
        import traceback
        try:
            self.progress.emit("正在分析文档...")

            result_parts = []
            char_count = 0

            for chunk in self.generator.generate(self.req_source, self.prd_source):
                if not self._is_running:
                    break

                result_parts.append(chunk)
                char_count += len(chunk)

                if char_count % 500 == 0:
                    self.progress.emit(f"已生成 {char_count} 字符...")

            if self._is_running:
                full_result = "".join(result_parts)
                self.finished.emit(full_result)

        except Exception as e:
            error_detail = f"{str(e)}\n\n堆栈信息:\n{traceback.format_exc()[:1000]}"
            self.error.emit(error_detail)

    def stop(self):
        """停止生成"""
        self._is_running = False
        self.wait(1000)


# ============ 主窗口类 ============

class TestPointGeneratorApp(QMainWindow):
    """测试点生成器主窗口"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.generator = None
        self.current_result = ""
        self.worker = None
        self.init_ui()
        self.load_config()
        self.apply_styles()

    def init_ui(self):
        """初始化UI - 添加滚动支持"""
        self.setWindowTitle("测试点生成器 v1.3")
        self.setGeometry(100, 100, 1400, 900)

        # ===== 创建滚动区域（新增）=====
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 关键：允许内容自适应大小
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 禁用水平滚动条
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 按需显示垂直滚动条
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # ===== 中央部件（内容容器）=====
        central_widget = QWidget()
        scroll_area.setWidget(central_widget)  # 将内容部件放入滚动区域

        # 设置主窗口的中央部件为滚动区域
        self.setCentralWidget(scroll_area)

        # ===== 主布局 =====
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # 内容顶部对齐

        # ===== 配置区域 =====
        config_group = self._create_config_group()
        main_layout.addWidget(config_group)

        # ===== 输入区域 =====
        input_group = self._create_input_group()
        main_layout.addWidget(input_group, stretch=3)

        # ===== 操作按钮区域 =====
        button_layout = self._create_button_layout()
        main_layout.addLayout(button_layout)

        # ===== 参考示例区域（新增）=====
        reference_group = self._create_reference_group()
        main_layout.addWidget(reference_group, stretch=1)

        # ===== 进度条 =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setMaximumHeight(30)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #333;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                color: #000;
                font-weight: bold;
                font-size: 13px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # ===== 结果展示区域 =====
        result_group = self._create_result_group()
        main_layout.addWidget(result_group, stretch=4)

        # 添加底部弹簧（可选，让内容紧凑顶部）
        # main_layout.addStretch()

        # 状态栏
        self.statusBar().showMessage("就绪 - 请选择文档或粘贴内容开始")
        self.statusBar().setStyleSheet("color: #000; font-size: 12px;")


    def _create_config_group(self) -> QGroupBox:
        """创建配置区域"""
        group = QGroupBox("🎁 免费AI模型配置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #000;
                border: 3px solid #2196F3;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 15px;
                padding-left: 20px;
                padding-right: 20px;
                background-color: #E3F2FD;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 15px;
                color: #1565C0;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # ===== 第一行：模型提供商选择 =====
        provider_layout = QHBoxLayout()
        provider_layout.setSpacing(15)

        provider_label = QLabel("选择平台:")
        provider_label.setStyleSheet("color: #000; font-size: 13px; font-weight: bold;")
        provider_layout.addWidget(provider_label)

        self.ai_combo = QComboBox()
        self.ai_combo.setMinimumWidth(400)
        self.ai_combo.setMinimumHeight(35)
        self.ai_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
                color: #000;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #000;
                selection-background-color: #2196F3;
            }
            QComboBox:hover {
                border: 2px solid #2196F3;
            }
        """)

        # 添加免费模型平台
        for key, info in Config.FREE_MODELS.items():
            display_text = f"{info['name']} | 免费额度：{info['free_quota']}"
            self.ai_combo.addItem(display_text, key)

        self.ai_combo.currentIndexChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.ai_combo, stretch=1)

        # 获取API Key按钮
        self.get_key_btn = QPushButton("🌐 获取API Key")
        self.get_key_btn.setMinimumHeight(35)
        self.get_key_btn.setMaximumWidth(130)
        self.get_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 5px;
                padding: 8px 15px;
                border: 2px solid #1976D2;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.get_key_btn.clicked.connect(self.open_api_key_url)
        provider_layout.addWidget(self.get_key_btn)

        layout.addLayout(provider_layout)

        # ===== 第二行：具体模型选择（新增）=====
        model_layout = QHBoxLayout()
        model_layout.setSpacing(15)

        model_label = QLabel("选择模型:")
        model_label.setStyleSheet("color: #000; font-size: 13px; font-weight: bold;")
        model_layout.addWidget(model_label)

        # 模型选择下拉框（动态根据平台变化）
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(350)
        self.model_combo.setMinimumHeight(35)
        self.model_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
                color: #000;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #000;
                selection-background-color: #4CAF50;
            }
            QComboBox:hover {
                border: 2px solid #4CAF50;
            }
        """)

        model_layout.addWidget(self.model_combo, stretch=1)
        model_layout.addStretch()

        layout.addLayout(model_layout)

        # ===== 第三行：API Key输入 =====
        key_layout = QHBoxLayout()
        key_layout.setSpacing(15)

        key_label = QLabel("API Key:")
        key_label.setStyleSheet("color: #000; font-size: 13px; font-weight: bold;")
        key_layout.addWidget(key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("在此粘贴API Key")
        self.api_key_input.setMinimumHeight(35)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 8px;
                background-color: white;
                color: #000;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 3px solid #4CAF50;
                background-color: #F1F8E9;
            }
        """)
        key_layout.addWidget(self.api_key_input, stretch=1)

        # 显示/隐藏按钮
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.setMaximumWidth(50)
        self.show_key_btn.setMinimumHeight(35)
        self.show_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                font-size: 14px;
                border-radius: 5px;
                border: 2px solid #616161;
            }
            QPushButton:checked {
                background-color: #4CAF50;
                border: 2px solid #388E3C;
            }
        """)
        self.show_key_btn.toggled.connect(self.toggle_key_visibility)
        key_layout.addWidget(self.show_key_btn)

        # 格式提示
        self.key_format_label = QLabel("格式: sk-xxx")
        self.key_format_label.setStyleSheet("""
            color: #D32F2F; 
            font-size: 12px; 
            font-weight: bold;
            min-width: 120px;
        """)
        key_layout.addWidget(self.key_format_label)

        layout.addLayout(key_layout)

        # ===== 第四行：保存按钮 =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_config_btn = QPushButton("💾 保存配置")
        self.save_config_btn.setMinimumHeight(40)
        self.save_config_btn.setMinimumWidth(150)
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                padding: 10px 20px;
                border: 3px solid #388E3C;
            }
            QPushButton:hover {
                background-color: #45a049;
                border: 3px solid #2E7D32;
            }
        """)
        self.save_config_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_config_btn)

        layout.addLayout(btn_layout)
        group.setLayout(layout)
        return group

    def on_provider_changed(self, index):
        """切换平台时更新模型列表"""
        provider = self.ai_combo.currentData()
        info = Config.FREE_MODELS.get(provider, {})

        # 更新格式提示
        self.key_format_label.setText(f"格式: {info.get('key_format', '')}")

        # 加载已保存的key
        key = self.config.get_key(provider)
        self.api_key_input.setText(key)

        # 更新模型列表
        self.model_combo.clear()

        if provider == "siliconflow":
            # 硅基流动模型列表
            models = [
                ("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "DeepSeek-R1-Distill-Qwen-32B（可能需权限）"),
                ("Qwen/Qwen2.5-72B-Instruct", "通义千问2.5-72B（推荐，最稳定）"),
                ("Qwen/Qwen2.5-32B-Instruct", "通义千问2.5-32B"),
                ("THUDM/GLM-Z1-32B-0414", "智谱GLM-Z1-32B-0414"),
                ("01-ai/Yi-1.5-34B-Chat", "零一万物Yi-1.5-34B"),
            ]
        elif provider == "claude_cli":
            # Claude CLI 本地模型
            models = [
                ("glm-5", "GLM-5（推荐）"),
                ("kimi-k2.5", "Kimi K2.5"),
                ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
                ("claude-opus-4-6", "Claude Opus 4.6"),
            ]
        elif provider == "openrouter":
            # OpenRouter模型列表（2024年3月）
            models = [
                ("google/gemma-2-9b-it:free", "Gemma 2 9B（推荐）"),
                ("microsoft/phi-3-medium-128k-instruct:free", "Phi-3 Medium"),
                ("mistralai/mistral-7b-instruct:free", "Mistral 7B"),
                ("huggingfaceh4/zephyr-7b-beta:free", "Zephyr 7B"),
            ]
        elif provider == "deepseek":
            models = [
                ("deepseek-chat", "DeepSeek-V3"),
                ("deepseek-reasoner", "DeepSeek-R1"),
            ]
        elif provider == "zhipu":
            models = [
                ("glm-4-flash", "GLM-4-Flash（免费版）"),
            ]
        else:
            models = []

        for model_id, display_name in models:
            self.model_combo.addItem(display_name, model_id)

        # 恢复保存的模型选择
        saved_model = getattr(self.config, f"{provider}_model", "")
        if saved_model:
            idx = self.model_combo.findData(saved_model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

        print(f"切换到平台: {provider}, 可用模型: {len(models)}个")

    def _create_input_group(self) -> QGroupBox:
        """创建输入区域 - 支持多文件PRD"""
        group = QGroupBox("📂 文档输入（支持本地文件或直接粘贴）")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #000;
                border: 3px solid #FF9800;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 15px;
                padding-left: 20px;
                padding-right: 20px;
                background-color: #FFF3E0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 15px;
                color: #E65100;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 使用分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #FF9800;
                border: 2px solid #E65100;
            }
        """)

        # ===== 需求文档区域 =====
        req_widget = QWidget()
        req_widget.setStyleSheet("background-color: #FFF8E1; border-radius: 8px;")
        req_layout = QVBoxLayout(req_widget)
        req_layout.setContentsMargins(15, 15, 15, 15)
        req_layout.setSpacing(12)

        # 文件选择 - 支持多文件
        req_file_layout = QHBoxLayout()
        req_file_layout.setSpacing(10)

        req_label = QLabel("📄 需求文档:")
        req_label.setStyleSheet("color: #000; font-size: 13px; font-weight: bold;")
        req_file_layout.addWidget(req_label)

        self.req_path_input = QLineEdit()
        self.req_path_input.setPlaceholderText("点击浏览选择文件，或输入路径（多文件用分号分隔）...")
        self.req_path_input.setMinimumHeight(32)
        self.req_path_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                color: #000;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 3px solid #FF9800;
            }
        """)
        req_file_layout.addWidget(self.req_path_input)

        self.req_browse_btn = QPushButton("浏览...")
        self.req_browse_btn.setMaximumWidth(80)
        self.req_browse_btn.setMinimumHeight(32)
        self.req_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #F57C00;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        # 修改为调用多文件浏览
        self.req_browse_btn.clicked.connect(self.browse_req_files)
        req_file_layout.addWidget(self.req_browse_btn)

        req_layout.addLayout(req_file_layout)

        # 添加多文件提示
        req_multi_hint = QLabel("💡 支持多文件：可一次选择多个需求文档，自动合并处理")
        req_multi_hint.setStyleSheet("color: #E65100; font-size: 11px; font-weight: bold;")
        req_layout.addWidget(req_multi_hint)

        # 文本输入标签
        req_text_label = QLabel("或直接粘贴内容：")
        req_text_label.setStyleSheet("color: #000; font-size: 12px; font-weight: bold; margin-top: 5px;")
        req_layout.addWidget(req_text_label)

        # 文本输入框
        self.req_text = QTextEdit()
        self.req_text.setPlaceholderText(
            "在此粘贴需求文档内容...\n"
            "支持Markdown、纯文本、Word、PDF等\n"
            "如果上方选择了文件，此处内容将被忽略"
        )
        font = QFont("Menlo", 12) if sys.platform == "darwin" else QFont("Consolas", 11)
        self.req_text.setFont(font)
        self.req_text.setStyleSheet("""
            QTextEdit {
                border: 3px solid #666;
                border-radius: 6px;
                padding: 10px;
                background-color: white;
                color: #000;
                font-size: 13px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 3px solid #FF9800;
                background-color: #FFFDE7;
            }
        """)
        req_layout.addWidget(self.req_text)

        # 格式提示
        req_hint = QLabel("💡 支持格式：.md .txt .docx .pdf .doc .html | 文件路径或纯文本")
        req_hint.setStyleSheet("color: #5D4037; font-size: 11px; font-weight: bold;")
        req_layout.addWidget(req_hint)

        # ===== PRD文档区域（修改为多文件支持）=====
        prd_widget = QWidget()
        prd_widget.setStyleSheet("background-color: #E8F5E9; border-radius: 8px;")
        prd_layout = QVBoxLayout(prd_widget)
        prd_layout.setContentsMargins(15, 15, 15, 15)
        prd_layout.setSpacing(12)

        # 文件选择 - 改为支持多文件
        prd_file_layout = QHBoxLayout()
        prd_file_layout.setSpacing(10)

        prd_label = QLabel("🎨 PRD文档:")
        prd_label.setStyleSheet("color: #000; font-size: 13px; font-weight: bold;")
        prd_file_layout.addWidget(prd_label)

        self.prd_path_input = QLineEdit()
        self.prd_path_input.setPlaceholderText("点击浏览选择文件，或输入路径（多文件用分号分隔）...")
        self.prd_path_input.setMinimumHeight(32)
        self.prd_path_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                color: #000;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 3px solid #4CAF50;
            }
        """)
        prd_file_layout.addWidget(self.prd_path_input)

        self.prd_browse_btn = QPushButton("浏览...")
        self.prd_browse_btn.setMaximumWidth(80)
        self.prd_browse_btn.setMinimumHeight(32)
        self.prd_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #388E3C;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        # 修改为调用多文件浏览
        self.prd_browse_btn.clicked.connect(self.browse_prd_files)
        prd_file_layout.addWidget(self.prd_browse_btn)

        prd_layout.addLayout(prd_file_layout)

        # 添加多文件提示
        prd_multi_hint = QLabel("💡 支持多文件：可一次选择多个PRD，自动合并处理")
        prd_multi_hint.setStyleSheet("color: #2E7D32; font-size: 11px; font-weight: bold;")
        prd_layout.addWidget(prd_multi_hint)

        # 文本输入标签
        prd_text_label = QLabel("或直接粘贴内容：")
        prd_text_label.setStyleSheet("color: #000; font-size: 12px; font-weight: bold; margin-top: 5px;")
        prd_layout.addWidget(prd_text_label)

        # 文本输入框
        self.prd_text = QTextEdit()
        self.prd_text.setPlaceholderText(
            "在此粘贴PRD文档内容...\n"
            "产品设计文档、原型说明、交互稿等\n"
            "支持Markdown、纯文本、Word、PDF等\n"
            "如果上方选择了文件，此处内容将被忽略"
        )
        self.prd_text.setFont(font)
        self.prd_text.setStyleSheet("""
            QTextEdit {
                border: 3px solid #666;
                border-radius: 6px;
                padding: 10px;
                background-color: white;
                color: #000;
                font-size: 13px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 3px solid #4CAF50;
                background-color: #F1F8E9;
            }
        """)
        prd_layout.addWidget(self.prd_text)

        # 格式提示
        prd_hint = QLabel("💡 支持格式：.md .txt .docx .pdf .xmind | 多文件用分号(;)分隔")
        prd_hint.setStyleSheet("color: #1B5E20; font-size: 11px; font-weight: bold;")
        prd_layout.addWidget(prd_hint)

        # 添加到分割器
        splitter.addWidget(req_widget)
        splitter.addWidget(prd_widget)
        splitter.setSizes([700, 700])

        layout.addWidget(splitter)
        group.setLayout(layout)
        return group

    def browse_prd_files(self):
        """浏览多个PRD文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择PRD文档（可多选）",
            str(Path.home()),
            "PRD文档 (*.pdf *.docx *.md *.txt *.xmind);;所有文件 (*.*)"
        )
        if file_paths:
            self.prd_path_input.setText('; '.join(file_paths))
            self.statusBar().showMessage(f"已选择 {len(file_paths)} 个PRD文件", 3000)

    def browse_req_files(self):
        """浏览多个需求文档文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择需求文档（可多选）",
            str(Path.home()),
            "文档文件 (*.md *.txt *.docx *.pdf *.doc *.html *.htm);;所有文件 (*.*)"
        )
        if file_paths:
            self.req_path_input.setText('; '.join(file_paths))
            self.statusBar().showMessage(f"已选择 {len(file_paths)} 个需求文档", 3000)


    def _create_button_layout(self) -> QHBoxLayout:
        """创建操作按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(20)

        # 生成按钮
        self.generate_btn = QPushButton("🚀 开始生成测试点")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setMinimumWidth(200)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 12px 30px;
                border: 3px solid #2E7D32;
            }
            QPushButton:hover {
                background-color: #45a049;
                border: 3px solid #1B5E20;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: 3px solid #9E9E9E;
            }
        """)
        self.generate_btn.clicked.connect(self.start_generation)
        layout.addWidget(self.generate_btn)

        # 停止按钮
        self.stop_btn = QPushButton("⏹ 停止生成")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setMinimumWidth(150)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                padding: 12px 25px;
                border: 3px solid #D32F2F;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: 3px solid #9E9E9E;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_generation)
        layout.addWidget(self.stop_btn)

        layout.addSpacing(40)

        # 导出按钮
        self.export_xmind_btn = QPushButton("📊 导出 XMind")
        self.export_xmind_btn.setMinimumHeight(45)
        self.export_xmind_btn.setMinimumWidth(150)
        self.export_xmind_btn.setEnabled(False)
        self.export_xmind_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
                border: 3px solid #1976D2;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: 3px solid #9E9E9E;
            }
        """)
        self.export_xmind_btn.clicked.connect(self.export_xmind)
        layout.addWidget(self.export_xmind_btn)

        self.export_md_btn = QPushButton("📝 导出 Markdown")
        self.export_md_btn.setMinimumHeight(45)
        self.export_md_btn.setMinimumWidth(150)
        self.export_md_btn.setEnabled(False)
        self.export_md_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
                border: 3px solid #F57C00;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: 3px solid #9E9E9E;
            }
        """)
        self.export_md_btn.clicked.connect(self.export_markdown)
        layout.addWidget(self.export_md_btn)

        layout.addStretch()
        return layout

    def _create_reference_group(self) -> QGroupBox:
        """创建历史测试点参考区域"""
        group = QGroupBox("📚 历史测试点参考（可选）- 让AI学习你的写作风格")
        group.setCheckable(True)  # 可折叠
        group.setChecked(False)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #000;
                border: 3px solid #607D8B;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 15px;
                padding-left: 20px;
                padding-right: 20px;
                background-color: #ECEFF1;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 15px;
                color: #455A64;
            }
            QGroupBox:checked {
                border: 3px solid #455A64;
                background-color: #CFD8DC;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 说明文字
        hint = QLabel(
            "💡 上传你之前写过的测试点文档，AI会分析你的写作风格（层级结构、术语、优先级标注方式等），生成风格一致的测试点")
        hint.setStyleSheet("color: #37474F; font-size: 12px; font-weight: bold;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 多文件选择
        file_layout = QHBoxLayout()

        self.ref_paths_input = QLineEdit()
        self.ref_paths_input.setPlaceholderText("可选择多个文件，用分号分隔...")
        self.ref_paths_input.setMinimumHeight(32)
        self.ref_paths_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #666;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                color: #000;
                font-size: 12px;
            }
        """)
        file_layout.addWidget(self.ref_paths_input)

        self.ref_browse_btn = QPushButton("浏览...")
        self.ref_browse_btn.setMaximumWidth(80)
        self.ref_browse_btn.setMinimumHeight(32)
        self.ref_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #455A64;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
        self.ref_browse_btn.clicked.connect(self.browse_reference_files)
        file_layout.addWidget(self.ref_browse_btn)

        layout.addLayout(file_layout)

        # 粘贴区域
        paste_label = QLabel("或直接粘贴历史测试点内容：")
        paste_label.setStyleSheet("color: #000; font-size: 12px; font-weight: bold;")
        layout.addWidget(paste_label)

        self.ref_text = QTextEdit()
        self.ref_text.setPlaceholderText(
            "在此粘贴你之前写的测试点...\n"
            "支持多个示例，用 --- 分隔\n"
            "例如：\n"
            "# 登录模块测试点\n"
            "## 正常登录\n"
            "- 输入正确账号密码，点击登录 [P0]\n"
            "- 验证token正确存储 [P1]\n"
            "---\n"
            "# 支付模块测试点\n"
            "## 微信支付\n"
            "- 调起微信SDK [P0]\n"
            "..."
        )
        self.ref_text.setMaximumHeight(150)  # 限制高度
        font = QFont("Menlo", 11) if sys.platform == "darwin" else QFont("Consolas", 10)
        self.ref_text.setFont(font)
        self.ref_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #666;
                border-radius: 6px;
                padding: 10px;
                background-color: white;
                color: #000;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.ref_text)

        # 风格预览按钮
        preview_layout = QHBoxLayout()
        preview_layout.addStretch()

        self.preview_style_btn = QPushButton("🔍 预览分析的风格")
        self.preview_style_btn.setMinimumHeight(35)
        self.preview_style_btn.setStyleSheet("""
            QPushButton {
                background-color: #78909C;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #546E7A;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        self.preview_style_btn.clicked.connect(self.preview_writing_style)
        preview_layout.addWidget(self.preview_style_btn)

        layout.addLayout(preview_layout)

        group.setLayout(layout)
        return group

    def browse_reference_files(self):
        """浏览多个参考文件 - 支持 XMind"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择历史测试点文档（可多选）",
            str(Path.home()),
            "所有支持格式 (*.md *.txt *.docx *.pdf *.xmind);;"
            "XMind 文件 (*.xmind);;"
            "文档文件 (*.md *.txt *.docx *.pdf);;"
            "所有文件 (*.*)"
        )
        if file_paths:
            self.ref_paths_input.setText('; '.join(file_paths))
            # 统计各类型文件数量
            xmind_count = sum(1 for p in file_paths if p.endswith('.xmind'))
            other_count = len(file_paths) - xmind_count
            msg = f"已选择 {len(file_paths)} 个参考文件"
            if xmind_count > 0:
                msg += f"（含 {xmind_count} 个 XMind）"
            self.statusBar().showMessage(msg, 3000)

    def preview_writing_style(self):
        """预览分析出的写作风格"""
        sources = self._get_reference_sources()
        if not sources:
            QMessageBox.information(self, "提示", "请先上传或粘贴历史测试点")
            return

        fetcher = ReferenceFetcher()
        result = fetcher.fetch_reference_examples(sources)

        style_guide = result.get('style_guide', '未能分析出风格')

        QMessageBox.information(
            self,
            "检测到的写作风格",
            style_guide + "\n\n找到 " + str(len(result.get('examples', []))) + " 个参考示例"
        )

    def _get_reference_sources(self) -> List[str]:
        """获取所有参考来源"""
        sources = []

        # 文件路径
        paths_text = self.ref_paths_input.text().strip()
        if paths_text:
            sources.extend([p.strip() for p in paths_text.split(';') if p.strip()])

        # 粘贴的文本（按 --- 分割多个示例）
        pasted = self.ref_text.toPlainText().strip()
        if pasted:
            examples = [ex.strip() for ex in pasted.split('---') if ex.strip()]
            sources.extend(examples)

        return sources


    def _create_result_group(self) -> QGroupBox:
        """创建结果展示区域"""
        group = QGroupBox("📋 生成结果（可直接编辑）")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #000;
                border: 3px solid #9C27B0;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                padding-bottom: 15px;
                padding-left: 20px;
                padding-right: 20px;
                background-color: #F3E5F5;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 15px;
                color: #7B1FA2;
            }
        """)

        layout = QVBoxLayout()

        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("生成的测试点将显示在这里...\n\n支持直接编辑修改，然后导出为XMind或Markdown")
        font = QFont("Menlo", 13) if sys.platform == "darwin" else QFont("Consolas", 12)
        self.result_text.setFont(font)
        self.result_text.setStyleSheet("""
            QTextEdit {
                border: 3px solid #666;
                border-radius: 8px;
                padding: 15px;
                background-color: white;
                color: #000;
                font-size: 14px;
                line-height: 1.6;
            }
            QTextEdit:focus {
                border: 3px solid #9C27B0;
                background-color: #FFF3E0;
            }
        """)
        layout.addWidget(self.result_text)
        group.setLayout(layout)
        return group

    def apply_styles(self):
        """应用全局样式"""
        # 设置全局调色板确保文字可见
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f5f5f5"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f0f0"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#000000"))
        self.setPalette(palette)

    # ============ 配置相关方法 ============

    def load_config(self):
        """加载保存的配置"""
        provider = self.config.default_ai
        index = self.ai_combo.findData(provider)
        if index >= 0:
            self.ai_combo.setCurrentIndex(index)
        self.on_provider_changed(index if index >= 0 else 0)


    def on_model_changed(self, index):
        """切换模型时更新"""
        provider = self.ai_combo.currentData()
        info = Config.FREE_MODELS.get(provider, {})
        self.key_format_label.setText(f"格式: {info.get('key_format', '')}")
        key = self.config.get_key(provider)
        self.api_key_input.setText(key)

    def open_api_key_url(self):
        """打开API Key获取页面"""
        provider = self.ai_combo.currentData()
        info = Config.FREE_MODELS.get(provider, {})
        url = info.get('url', '')
        if url:
            webbrowser.open(url)
            self.statusBar().showMessage(f"已打开 {info.get('name')} 官网", 5000)

    def toggle_key_visibility(self, checked):
        """切换API Key显示/隐藏"""
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🙈")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("👁")

    def save_config(self):
        """保存配置"""
        provider = self.ai_combo.currentData()
        api_key = self.api_key_input.text().strip()
        selected_model = self.model_combo.currentData() if self.model_combo.count() > 0 else None

        # Claude CLI 不需要 API Key
        if provider == "claude_cli":
            if selected_model:
                self.config.claude_cli_model = selected_model
            self.config.default_ai = provider
            self.config.save()
            QMessageBox.information(self, "保存成功",
                                    f"已保存 Claude CLI 配置！\n"
                                    f"模型：{selected_model or 'glm-5'}")
            return

        if not api_key:
            QMessageBox.warning(self, "提示", "请输入API Key")
            return

        # 验证智谱格式
        if provider == "zhipu" and "." not in api_key:
            QMessageBox.warning(self, "格式错误",
                                "智谱API Key格式应为：id.secret（包含小数点）")
            return

        # 保存配置
        self.config.set_key(provider, api_key)
        if selected_model:
            setattr(self.config, f"{provider}_model", selected_model)
        self.config.default_ai = provider
        self.config.save()

        QMessageBox.information(self, "✅ 保存成功",
                                f"已保存 {Config.FREE_MODELS[provider]['name']} 的配置！\n"
                                f"选用模型: {self.model_combo.currentText() if self.model_combo.count() > 0 else '默认'}\n"
                                f"免费额度：{Config.FREE_MODELS[provider]['free_quota']}")

    # ============ 文件操作 ============

    def browse_file(self, target_input: QLineEdit):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            str(Path.home()),
            "文档文件 (*.md *.txt *.docx *.pdf *.doc *.html *.htm);;所有文件 (*.*)"
        )
        if file_path:
            target_input.setText(file_path)
            try:
                size = Path(file_path).stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
                self.statusBar().showMessage(f"已选择: {Path(file_path).name} ({size_str})", 3000)
            except:
                pass

    def get_input_content(self, path_input: QLineEdit, text_edit: QTextEdit) -> str:
        """获取输入内容"""
        pasted = text_edit.toPlainText().strip()
        if pasted:
            return pasted

        path = path_input.text().strip()
        if not path:
            raise ValueError("请选择文件或粘贴文档内容")

        return path

    # ============ 生成控制 ============

    def start_generation(self):
        """开始生成测试点 - 修复版"""
        provider = self.ai_combo.currentData()

        # Claude CLI 不需要 API Key
        if provider != "claude_cli":
            api_key = self.api_key_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "错误", "请先配置API Key！")
                return

        try:
            req_content = self.get_input_content(self.req_path_input, self.req_text)
            prd_content = self.get_input_content(self.prd_path_input, self.prd_text)
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", str(e))
            return

        self.save_config()

        # 创建AI客户端
        ai_client = self.config.get_ai_client()
        if not ai_client:
            QMessageBox.critical(self, "配置错误", "无法初始化AI客户端")
            return

        # 创建生成器
        analyzer = RequirementAnalyzer()
        self.generator = TestPointGenerator(ai_client, analyzer)

        # 设置参考示例（修复：在创建generator之后调用）
        reference_sources = self._get_reference_sources()
        if reference_sources:
            self.generator.set_reference_examples(reference_sources)
            self.statusBar().showMessage(f"已加载 {len(reference_sources)} 个风格参考示例...", 2000)

        # 创建工作线程
        self.worker = GenerationWorker(self.generator, req_content, prd_content)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.generation_finished)
        self.worker.error.connect(self.generation_error)

        # UI状态更新
        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_xmind_btn.setEnabled(False)
        self.export_md_btn.setEnabled(False)
        self.result_text.clear()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("正在初始化...")

        self.worker.start()
        self.statusBar().showMessage("正在生成测试点...")

    def stop_generation(self):
        """停止生成"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.statusBar().showMessage("已停止生成", 3000)

        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("已停止")

    def update_progress(self, message: str):
        """更新进度"""
        self.statusBar().showMessage(message)
        self.progress_bar.setFormat(message)

    def generation_finished(self, result: str):
        """生成完成"""
        self.current_result = result
        self.result_text.setPlainText(result)

        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_xmind_btn.setEnabled(True)
        self.export_md_btn.setEnabled(True)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("✅ 完成")

        char_count = len(result)
        self.statusBar().showMessage(f"生成完成！共 {char_count} 字符", 5000)

        reply = QMessageBox.question(
            self,
            "生成成功",
            f"已成功生成 {char_count} 字符的测试点！\n\n是否立即导出为XMind思维导图？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.export_xmind()

    def generation_error(self, error_msg: str):
        """生成出错"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("❌ 失败")

        QMessageBox.critical(self, "生成失败",
                             f"错误信息:\n{error_msg}\n\n"
                             f"常见解决方法:\n"
                             f"1. 检查API Key是否正确\n"
                             f"2. 检查网络连接\n"
                             f"3. 尝试切换其他免费模型")

        self.statusBar().showMessage("生成失败", 3000)

    # ============ 导出功能 ============

    def export_xmind(self):
        """导出为XMind格式（使用OPML作为稳定备选）"""
        if not self.current_result:
            QMessageBox.warning(self, "错误", "没有可导出的内容")
            return

        # 让用户选择格式
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QRadioButton

        dialog = QDialog(self)
        dialog.setWindowTitle("选择导出格式")
        layout = QVBoxLayout(dialog)

        rb1 = QRadioButton("XMind格式 (.xmind) - 需要安装xmind库")
        rb1.setChecked(True)
        rb2 = QRadioButton("OPML格式 (.opml) - 最稳定，XMind直接支持")
        rb3 = QRadioButton("Markdown (.md) - 通用格式")

        layout.addWidget(rb1)
        layout.addWidget(rb2)
        layout.addWidget(rb3)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # 根据选择导出
        if rb1.isChecked():
            self._export_xmind_native()
        elif rb2.isChecked():
            self._export_opml()
        else:
            self.export_markdown()

    def _export_xmind_native(self):
        """原生XMind导出"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存XMind文件",
            str(Path.home() / "测试点分析.xmind"),
            "XMind文件 (*.xmind)"
        )

        if not file_path:
            return

        if not file_path.endswith('.xmind'):
            file_path += '.xmind'

        try:
            exporter = XMindExporter()
            exporter.export_from_markdown(self.current_result, file_path)

            QMessageBox.information(self, "✅ 导出成功",
                                    f"已保存到:\n{file_path}")

        except Exception as e:
            # 失败时建议使用OPML
            QMessageBox.warning(self, "导出失败",
                                f"XMind格式导出失败:\n{str(e)}\n\n")

            # 自动切换到OPML
            self._export_opml()

    def _export_opml(self):
        """OPML格式导出（最稳定）"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存OPML文件",
            str(Path.home() / "测试点分析.opml"),
            "OPML文件 (*.opml);;XML文件 (*.xml)"
        )

        if not file_path:
            return

        if not file_path.endswith('.opml'):
            file_path += '.opml'

        try:
            exporter = MarkdownExporter()
            exporter.export_opml(self.current_result, file_path)  # 使用正确的方法名

            QMessageBox.information(self, "✅ 导出成功",
                                    f"已保存OPML格式到:\n{file_path}\n\n"
                                    f"导入XMind方法:\n"
                                    f"1. 打开XMind软件\n"
                                    f"2. 文件 → 导入 → OPML\n"
                                    f"3. 选择此文件即可")

        except Exception as e:
            QMessageBox.critical(self, "❌ 导出失败", f"OPML导出失败:\n{str(e)}")
            import traceback
            print(traceback.format_exc())  # 打印详细错误到控制台

    def export_markdown(self):
        """导出为Markdown"""
        if not self.current_result:
            QMessageBox.warning(self, "错误", "没有可导出的内容")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存Markdown文件",
            str(Path.home() / "测试点分析.md"),
            "Markdown文件 (*.md);;文本文件 (*.txt)"
        )

        if not file_path:
            return

        try:
            exporter = MarkdownExporter()
            exporter.export(self.current_result, file_path)

            QMessageBox.information(self, "导出成功",
                                    f"已保存到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败:\n{str(e)}")




# ============ 程序入口 ============

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 强制设置全局样式确保可见性
    app.setStyleSheet("""
        QWidget {
            color: #000000;
        }
        QToolTip {
            color: #000000;
            background-color: #FFFFE0;
            border: 1px solid #000000;
        }
    """)

    window = TestPointGeneratorApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()