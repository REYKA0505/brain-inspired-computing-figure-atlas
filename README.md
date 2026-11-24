# 类脑计算科研图谱

`brain-inspired-computing-figure-atlas`

积累类脑计算领域可追溯的科研绘图参考。图库以类脑模型、储备池计算和神经形态器件为主线，收录神经环路、脑图谱和复杂系统相关图件作为交叉参考。

## 浏览

- **网页图库**　下载仓库后在浏览器打开 [index.html](index.html)，可离线筛选和放大图例。
- **Obsidian 图墙**　在 Obsidian 中打开项目目录，从[图墙索引](docs/index.md)按研究主题读图。
- **站外资源**　[资源索引](docs/resources.md)收录论文图集、图片检索平台和科研插画素材库。

## 目录

```text
index.html          网页图库入口
assets/             样式、交互脚本和图片预览
  images/           WebP 图例
data/               来源清单、网页数据和采集记录
docs/               主题图墙与外部资源索引
  topics/           各研究主题的 Obsidian 图墙
tools/              图例采集与图库构建脚本
```

## 维护

现有快照以 [data/sources.json](data/sources.json) 为准。编辑图例元数据后，可在项目根目录离线重建网页数据和图墙。

```bash
python3 tools/build_gallery.py --from-manifest
```

扩充图库时，可在 `SELECTED` 中添加论文 PMCID，也可在 [图件选录清单](data/curated-figures.json) 中登记预印本和选定图件。预印本记录采用具体版本的图注、原图地址和许可出处。安装采集依赖后，可增量处理选录图件。

```bash
python3 -m pip install -r tools/requirements.txt
python3 tools/build_gallery.py --update-curated
```

从预印本 PDF 提取图件时还需要 `pdftoppm`（Poppler）。全量更新 PMC 和选录图件使用同一构建入口。

```bash
python3 tools/build_gallery.py
```

## 来源与许可

本地图件为原图的缩放预览，保留论文标题、DOI、图号、图注、原图链接和文章级许可。收录论文的文章级许可为 CC BY 4.0，图中第三方素材可能另有许可。引用、改编或公开传播前，请核对原图的署名和许可。[来源清单](data/sources.json)

研究主题按论文内容整理，图形线索由英文图注关键词识别，可能存在误标或漏标。
