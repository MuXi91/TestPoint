# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TestPoint is a PyQt6 desktop application that generates test points from requirement documents and PRD documents using AI APIs. It supports multiple AI providers (SiliconFlow, DeepSeek, Zhipu, OpenRouter) and can export results to XMind or Markdown format.

## Commands

```bash
# Run the application
python main.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python test.py
python test_api.py
```

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

### Key Modules

- **config.py**: Manages API keys and model configuration. Loads from environment variables first, then config file (`~/.test_generator_config.json`).

- **api_clients/**: AI provider implementations. Each client has `generate_test_points(requirement, prd)` returning a streaming iterator. SiliconFlow is the default provider.

- **core/test_generator.py**: Main orchestration logic. Coordinates document fetching, analysis, and AI generation.

- **core/analyzer.py**: Pre-analyzes documents to extract modules, user stories, business rules, and UI components.

- **document_fetchers/**: Fetches content from various sources:
  - `local_fetcher.py`: Local files (.md, .txt, .docx, .pdf)
  - `lanhu_fetcher.py`: Lanhu (蓝湖) URLs via Selenium
  - `reference_fetcher.py`: Reference examples for style matching

- **exporters/**: Output formatting:
  - `xmind_exporter.py`: XMind format (ZIP containing content.xml, styles.xml, comments.xml)
  - `markdown_exporter.py`: Markdown and OPML formats

### Data Flow

1. User provides requirement source (file path or text) and PRD source (Lanhu URL, file, or text)
2. Document fetchers extract content from sources
3. Analyzer pre-processes documents
4. AI client generates test points via streaming API
5. Results displayed in GUI, exportable to XMind/Markdown

## API Configuration

API keys can be set via:
1. Environment variables: `SILICONFLOW_KEY`, `DEEPSEEK_KEY`, `ZHIPU_KEY`, `OPENROUTER_KEY`
2. Config file: `~/.test_generator_config.json`
3. GUI settings dialog

Default AI provider: SiliconFlow with model `Qwen/Qwen2.5-72B-Instruct`

## XMind Export Notes

The xmind library requires `ownerWorkbook` parameter when creating `TopicElement`:

Save using `xmind.save()` or `WorkbookSaver` class, not `saver.save()`.