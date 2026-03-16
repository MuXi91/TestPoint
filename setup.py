from setuptools import setup, find_packages

setup(
    name="test-point-generator",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.4.0",
        "requests>=2.31.0",
        "xmind>=1.2.0",
        "beautifulsoup4>=4.12.0",
        "lark-oapi>=1.0.0",
        "selenium>=4.15.0",
        "openai>=1.0.0",
        "anthropic>=0.8.0",
        "markdown>=3.5.0",
        "webdriver-manager>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "test-generator=main:main",
        ],
    },
    python_requires=">=3.9",
)