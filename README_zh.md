# nlm-unwatermark

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)
[![GitHub stars](https://img.shields.io/github/stars/encoreshao/nlm-unwatermark?style=social)](https://github.com/encoreshao/nlm-unwatermark/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/encoreshao/nlm-unwatermark)](https://github.com/encoreshao/nlm-unwatermark/issues)

[English](README.md) | [中文](README_zh.md) | [Français](README_fr.md) | [日本語](README_ja.md)

使用计算机视觉图像修复技术，从 PDF、PPTX 及图片导出文件（PNG/JPG/WEBP）中移除「NotebookLM」水印 —— 不是简单地用纯色方块覆盖，因此渐变、纹理和幻灯片边框都能完整保留。

## 目录

- [工作原理](#工作原理)
- [环境要求](#环境要求)
- [安装](#安装)
- [使用方法](#使用方法)
  - [参数说明](#参数说明)
- [独立可执行文件](#独立可执行文件)
- [项目结构](#项目结构)
- [开发](#开发)
- [参与贡献](#参与贡献)
- [法律声明与合理使用](#法律声明与合理使用)
- [许可证](#许可证)

## 工作原理

1. **检测** —— 通过对比度分析与文字模板匹配定位水印，并忽略附近的幻灯片内容。
2. **重建** —— 从同一页面附近的干净区域修复水印下方的背景（找不到干净区域时回退到图像修复算法）。
3. **修补** —— PDF 会直接从文本层删除水印文字（属于删改/redaction，而非覆盖），并对图标做一次小范围的像素级修补；PPTX 与图片则直接在渲染像素上修补。

## 环境要求

- Python 3.9 及以上版本
- pip
- 依赖项（会自动安装）：[PyMuPDF](https://pypi.org/project/PyMuPDF/)、[Pillow](https://pypi.org/project/Pillow/)、[opencv-python-headless](https://pypi.org/project/opencv-python-headless/)、[NumPy](https://pypi.org/project/numpy/)、[tqdm](https://pypi.org/project/tqdm/)

## 安装

```bash
git clone https://github.com/encoreshao/nlm-unwatermark.git
cd nlm-unwatermark
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .           # 可选 —— 安装后可直接使用 `nlm-unwatermark` 命令
```

验证安装是否成功：

```bash
nlm-unwatermark --help
```

如果能看到用法说明，就说明安装成功了。

## 使用方法

```bash
nlm-unwatermark file.pdf                # → file_cleaned.pdf
nlm-unwatermark file.pptx                # → file_cleaned.pptx
nlm-unwatermark slide.png                # → slide_cleaned.png
nlm-unwatermark ./my_folder/             # 批量处理文件夹中所有支持的文件
nlm-unwatermark file.pdf --preview       # 仅 PDF：只处理第一页
nlm-unwatermark file.pdf -o out.pdf      # 自定义输出路径
```

没有执行 `pip install -e .`？可以改用 `python -m nlm_unwatermark file.pdf`，效果相同。

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `-o`, `--output` | `<文件名>_cleaned.<扩展名>` | 输出路径（仅单文件处理时生效） |
| `--preview` | 关闭 | 仅 PDF：只处理第一页 |
| `--margin-x` | `400` | 从右边缘开始的搜索宽度（像素） |
| `--margin-y` | `120` | 从底边缘开始的搜索高度（像素） |
| `--threshold` | `22` | 候选像素的对比度阈值 |
| `--text-threshold` | `0.33` | 判定为文字所需的模板匹配置信度 |
| `--scale` | `3.5` | PDF 渲染 / 图片放大倍率 |
| `--radius` | `3` | 图像修复半径（仅回退方案使用） |
| `--no-patch-heal` | 关闭 | 使用普通图像修复，而非干净区域修补 |
| `--debug` | 关闭 | 将检测到的掩码输出到 `debug_watermark/` |

## 独立可执行文件

不想搭建 Python 环境？可以为 Windows、macOS 和 Linux 构建单文件的独立可执行文件（无需解释器或依赖项）—— 详见下方[开发](#开发)一节。

```bash
# Windows
dist\nlm-unwatermark.exe file.pdf

# macOS / Linux
dist/nlm-unwatermark file.pdf
```

## 项目结构

```
nlm_unwatermark/
├── cli.py              命令行入口（nlm-unwatermark / python -m nlm_unwatermark）
├── config.py            可调节的检测/去除参数
├── detection.py          水印定位（候选提取 + 模板匹配）
├── reconstruction.py      背景修复 / 图像修复
├── engine.py              串联检测与重建逻辑
└── formats/               各格式处理器：pdf.py、image.py、pptx.py
packaging/
├── entry_point.py         PyInstaller 专用的绝对导入入口
└── nlm-unwatermark.spec   PyInstaller 构建配置
docs/
└── BUILD.md               独立可执行文件构建说明
```

## 开发

按照[安装](#安装)一节搭建本地开发环境；如果打算打包可执行文件，还需安装构建专用依赖：

```bash
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm
```

完整构建细节 —— 包括为什么配置文件指向 `packaging/entry_point.py` 而非 `nlm_unwatermark/__main__.py` —— 请参见 [docs/BUILD.md](docs/BUILD.md)。

检测/去除逻辑的调优参数（搜索边距、阈值、修复半径等）定义在 `nlm_unwatermark/config.py` 中，并通过 `nlm_unwatermark/cli.py` 暴露为命令行参数 —— 参见上方[参数说明](#参数说明)表格。

## 参与贡献

欢迎提交 Pull Request —— 较大的改动请先[提交 Issue](https://github.com/encoreshao/nlm-unwatermark/issues/new) 讨论。

## 法律声明与合理使用

请仅将本工具用于您合法拥有或有权修改的文档 —— 使用方式由您自行负责。当您拥有所生成内容的所有权时，移除水印是合法的（Google 表示不会声称拥有 NotebookLM 生成内容的所有权）；本工具旨在帮助您清理自己导出的内容。本软件基于 MIT 许可证提供，但不鼓励将其用于规避付费服务的归属或付费墙要求。

## 许可证

MIT © 2026 [Encore Shao](LICENSE)
