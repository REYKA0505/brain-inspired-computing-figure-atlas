---
name: atlas-resource-contribution
description: Verify and add paper figures or external scientific drawing resources to the Brain-Inspired Computing Figure Atlas. Use when a contributor provides a paper title, DOI, preprint, or resource URL and asks to prepare a gallery update or open a contribution PR.
---

# 为类脑计算科研图谱补充资源

克隆上游仓库或打开已有的个人 fork。以 `REYKA0505/brain-inspired-computing-figure-atlas` 的最新 `main` 为基线，从仓库根目录读取 `README.md` 和相关清单。[上游仓库](https://github.com/REYKA0505/brain-inspired-computing-figure-atlas)

## 核验候选

- 补充论文图件时，按贡献者给出的标题、DOI 或链接定位原文，核对题名、作者、出版年份和版本。预印本引用明确的版本，图件与许可须来自同一版本。
- 用 `data/sources.json` 和 `data/curated-figures.json` 查重。除了规范化后的 DOI 和图号，也比对题名与图面，避免把预印本和正式发表版的同一张图重复收录。优先选择类脑模型、神经形态器件及仓库已有研究主题下可作为绘图参考的图件。
- 查看原文许可及图注中的署名或第三方素材说明，确认具体图件适用 **CC BY 4.0** 后再发布预览。把能定位到许可声明的原始页面记为 `license_evidence`。许可或版本存疑时，列出待核验项和来源供贡献者确认，也可将候选留给维护者核验。[资源补充](https://github.com/REYKA0505/brain-inspired-computing-figure-atlas/issues/new?template=paper-suggestion.yml)

## 增补论文图件

1. 在 `data/curated-figures.json` 按相近条目的格式登记。论文记录填写 `source_id`、`category`、`paper`、`journal`、`year`、`author`、`doi`、`license` 和 `license_evidence`，预印本另填 `version`。主题采用 `tools/build_gallery.py` 的 `SELECTED` 中已有名称，DOI 使用不带网址前缀的标识，`license` 填 `https://creativecommons.org/licenses/by/4.0/`。
2. 在 `figures` 中填写每张图的 `id`、`label`、`figure_title`、`caption`、`tags`、`original` 和 `paper_url`。图号和图注与选定版本一致，图型标签沿用 `tools/build_gallery.py` 中 `TYPE_PATTERNS` 的名称。`original` 用可访问的 HTTPS 原图地址，`paper_url` 尽量定位到论文中的图。补同一版本的图时复用已有论文记录。构建出的 `source_id-id` 在图库中须唯一，只使用字母、数字、点、下划线和短横线。
3. 若只能从公开 PDF 提取图件，参考清单中带 `pdf_crop` 的记录。`original` 指向对应版本的 PDF，`pdf_crop.page` 从 1 起算，`pdf_crop.box` 是从页面左上角量起的 `[左, 上, 右, 下]`，单位为 PDF 点。检查裁切包含完整面板、轴标签和比例尺。
4. 在 Python 虚拟环境安装构建依赖后执行增量更新。PDF 裁切需要另装 Poppler 的 `pdftoppm`。

```bash
python3 -m pip install -r tools/requirements.txt
python3 tools/build_gallery.py --update-curated
```

提交选录清单和构建生成的 `assets/images/` 下的新 WebP 及相关页面和数据。`data/sources.json`、`data/figures.js`、采集记录和图墙由脚本生成。公开提交只包含已核验的预览与出处，原始 PDF、Zotero 附件和个人文件留在本地。

## 补充站外链接

在 `data/resources.json` 查重，再向合适分类的 `rows` 加一项。沿用 `name` 中的 `label`、HTTPS `url` 和 `description` 的现有格式，写明站点收录的图类。对方的图件留在原站，通过链接访问。

```bash
python3 tools/build_gallery.py --from-manifest
```

一并提交 `data/resources.json`、生成的 `resources.html` 和 `docs/resources.md`。同批也新增图件时，图件增量构建会同步刷新资源页。

## 验证与提交 PR

1. 执行 `git diff --check`，查看 `git status --short` 与完整差异。在浏览器打开 `index.html` 或 `resources.html`，按 DOI、题名或资源名找到新增条目，核对预览、来源和链接。预览失败或链接不可达时先修正，再提交能够验证的内容。
2. 贡献者要求提交 PR 时，使用其自己的 GitHub 账号和个人 fork，基于最新上游 `main` 建立 `codex/atlas-...` 分支。可用 `gh auth status` 确认账号，用 `gh repo fork REYKA0505/brain-inspired-computing-figure-atlas --clone` 建立 fork 并克隆，或复用现有 fork。检查实际推送地址，将本次改动和对应构建产物提交到个人 fork 的分支。
3. PR 标题使用「资源补充 · 论文短标题或资源站名」。正文列出各项来源和构建检查结果，图件附 DOI、图号、版本及许可声明的位置，资源站附官网链接。填写下列变量后，推送个人 fork 的分支并向上游 `main` 发起 PR，返回 PR 链接供贡献者查看。只请求准备改动时，交付本地变更及 PR 正文即可。

`ATLAS_FORK_REMOTE` 填个人 fork 的远程名称，`ATLAS_FORK_OWNER` 填贡献者的 GitHub 用户名，`ATLAS_BRANCH` 填工作分支，`ATLAS_PR_TITLE` 填标题，`ATLAS_PR_BODY` 填仓库外的正文文件路径。

```bash
git push "$ATLAS_FORK_REMOTE" "$ATLAS_BRANCH"
gh pr create --repo REYKA0505/brain-inspired-computing-figure-atlas --base main \
  --head "$ATLAS_FORK_OWNER:$ATLAS_BRANCH" --title "$ATLAS_PR_TITLE" \
  --body-file "$ATLAS_PR_BODY"
```

也可在 GitHub 的跨 fork 比较界面选择个人分支作为来源、`REYKA0505/brain-inspired-computing-figure-atlas:main` 作为目标，由维护者审核合并。[GitHub CLI 参考](https://cli.github.com/manual/gh_pr_create)
