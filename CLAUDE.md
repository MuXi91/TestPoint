# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

##项目概述

TestPoint是一个PyQt6桌面应用程序，它使用AI api从需求文档和PRD文档生成测试点。它支持多个AI提供商（SiliconFlow, DeepSeek, Zhipu, OpenRouter），并可以将结果导出到XMind或Markdown格式。
# #命令

”“bash
#运行应用程序
python main.py

#安装依赖项
PIP install -r requirements.txt

#运行测试
python test_api.py
' ' '

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (GUI)                        │
│  PyQt6 MainWindow - handles UI, threading, user interaction │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ config.py     │   │ core/           │   │ exporters/      │
│ - API keys    │   │ - analyzer.py   │   │ - xmind_exporter│
│ - model config│   │ - test_generator│   │ - markdown_exp. │
└───────────────┘   └─────────────────┘   └─────────────────┘
        │                     │
        ▼                     ▼
┌───────────────┐   ┌─────────────────┐
│ api_clients/  │   │ document_fetchers│
│ - siliconflow │   │ - local_fetcher │
│ - deepseek    │   │ - lanhu_fetcher │
│ - zhipu       │   │ - reference_... │
│ - openrouter  │   └─────────────────┘
└───────────────┘
```

关键模块

—**config.py**：管理API密钥和模型配置。首先从环境变量加载，然后从配置文件（' ~/.test_generator_config.json '）加载。

**api_clients/**: AI提供程序实现。每个客户端都有‘ generate_test_points(requirement, prd) ’返回一个流迭代器。SiliconFlow是默认的提供程序。

—**core/test_generator.py**：主业务流程逻辑。协调文档获取、分析和AI生成。

- **core/analyzer.py**：预分析文档以提取模块、用户故事、业务规则和UI组件。

**document_fetchers/**：从各种来源获取内容：
- ' local_fetcher.py '：本地文件.Md、.txt、.docx、.pdf)
- ' lanhu_fetcher.py '：通过Selenium获取Lanhu的url
- ' reference_fetcher.py '：样式匹配的参考示例

- **出口商/**：输出格式：
- ' xmind_export .py ': XMind格式（ZIP包含content.xml, styles.xml, comments.xml）
- ' markdown_exporters .py ': Markdown和OPML格式

###数据流

1. 用户提供需求源（文件路径或文本）和PRD源（Lanhu URL、文件或文本）
2. 文档获取器从源提取内容
3. 分析器预处理文件
4. AI客户端通过流API生成测试点
5. 结果显示在GUI中，可导出到XMind/Markdown

## API配置

API密钥可以通过以下方式设置：
1. 环境变量：‘ SILICONFLOW_KEY ’， ‘ DEEPSEEK_KEY ’
2. 配置文件：‘ ~/.test_generator_config.json ’
3. GUI设置对话框

默认AI提供商：SiliconFlow模型‘ Qwen/Qwen2.5-72B-Instruct ’

## XMind导出笔记

xmind库在创建“TopicElement”时需要“ownerWorkbook”参数：

使用xmind保存。save() ‘或’ WorkbookSaver ‘类，而不是’ save .save() '。