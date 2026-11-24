"""Build a local reference gallery from selected, CC-BY open-access articles."""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import io
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from string import Template
from subprocess import run
from tempfile import TemporaryDirectory
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = Path("assets/images")
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
MANIFEST = DATA_DIR / "sources.json"
CURATED = DATA_DIR / "curated-figures.json"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
FOCUS_TOPIC = "类脑计算与模型"
USER_AGENT = "ResearchFigureReferenceGallery/1.0 (educational local collection)"
SELECTED = {
    FOCUS_TOPIC: [
        "PMC10803782", "PMC8455577", "PMC7426273", "PMC7367848",
        "PMC10917819", "PMC9068614", "PMC7814066", "PMC8791835",
    ],
    "神经形态硬件": [],
    "果蝇与感觉": [
        "PMC11446842", "PMC11446831", "PMC11446845", "PMC11525180",
        "PMC11446846", "PMC12119369", "PMC11621569", "PMC8105414",
        "PMC7893153", "PMC11228034", "PMC12048489", "PMC12559195",
    ],
    "神经环路与决策": [
        "PMC11499283", "PMC11903320", "PMC12408363", "PMC12408349",
        "PMC10172131", "PMC10665198", "PMC9892006", "PMC9360402",
        "PMC7229188", "PMC6662698", "PMC10015009", "PMC8408193",
    ],
    "网络与复杂系统": [
        "PMC9649740", "PMC8342694", "PMC7930026", "PMC6465316",
        "PMC6707263", "PMC10761873", "PMC8149673", "PMC11161514",
    ],
    "群体行为与动力学": [
        "PMC8590009", "PMC7264142", "PMC8748659", "PMC9090766",
    ],
    "脑图谱与成像": [
        "PMC9021021", "PMC10060165", "PMC8497570", "PMC6814749",
        "PMC9381504", "PMC7801665", "PMC9395399", "PMC9038754",
    ],
}

TYPE_PATTERNS = {
    "示意图 / 方法": r"\b(schematic|illustrat(?:ion|ed)|diagram|workflow|pipeline|framework|experimental (?:design|setup|paradigm))\b",
    "网络 / 连接组": r"\b(network|connectome|connectivity|graph|connectomic|neuronal circuit)\b",
    "曲线 / 时间序列": r"\b(time (?:course|series)|trace|trajector\w*|dynamics|temporal|over time|response curve)\b",
    "热图 / 矩阵": r"\b(heat\s?map|matrix|matrices|correlation map)\b",
    "散点 / 降维": r"\b(scatter\s?plot|scatter plot|embedding|principal component|umap|t-sne|dimensionality reduction)\b",
    "显微 / 脑成像": r"\b(microscop\w*|imaging|fluorescen\w*|mri|confocal|brain images|stain\w*)\b",
    "统计 / 分布": r"\b(box ?plots?|violin plots?|bar plots?|histograms?|distributions?|statistical|quantification)\b",
}

# Exclude figures with indications of third-party artwork or a separate reuse credit.
EXTERNAL_CREDIT = re.compile(
    r"adapted from|modified from|reproduced from|reprinted from|"
    r"permission of|with permission|biorender|image credit|"
    r"copyright|creative commons|©|licensed under",
    re.IGNORECASE,
)
XLINK = "{http://www.w3.org/1999/xlink}href"


def get(url: str, attempts: int = 3) -> bytes:
    error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=35) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = exc
            time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"{url}: {error}")


def words(node) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def article(category: str, pmcid: str):
    from lxml import etree

    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(get(url), parser)
    meta = root.find("./front/article-meta")
    if meta is None:
        raise ValueError(f"{pmcid}: missing article metadata")

    license_links = meta.xpath("./permissions/license//ext-link/@xlink:href", namespaces={"xlink": "http://www.w3.org/1999/xlink"})
    license_url = next((link for link in license_links if re.search(r"creativecommons\.org/licenses/by/4\.0/?", link)), None)
    if not license_url:
        raise ValueError(f"{pmcid}: no explicit CC BY 4.0 article license")
    license_url = CC_BY

    title = words(meta.find("./title-group/article-title"))
    journal = words(root.find("./front/journal-meta/journal-title-group/journal-title"))
    doi = words(meta.find("./article-id[@pub-id-type='doi']"))
    year = next((words(y) for y in meta.xpath("./pub-date/year") if words(y)), "")
    first_author = meta.find("./contrib-group/contrib[@contrib-type='author']/name")
    surname = words(first_author.find("surname")) if first_author is not None else ""
    author = (surname + " et al.") if surname else "See paper"
    if not (title and doi and year):
        raise ValueError(f"{pmcid}: incomplete citation")

    results = []
    media_urls = None
    for fig in root.xpath("./body//fig[not(ancestor::fig)]"):
        fig_id = fig.get("id", "")
        label = words(fig.find("label"))
        caption = fig.find("caption")
        caption_text = words(caption)
        if not fig_id or not label or not caption_text or fig.find("permissions") is not None:
            continue
        if EXTERNAL_CREDIT.search(caption_text):
            continue
        graphic = None
        for candidate in fig.xpath(".//graphic[not(ancestor::caption)]"):
            href = candidate.get(XLINK, "")
            pi = candidate.xpath("processing-instruction('cloudpmc-path')")
            if not re.search(r"\.(jpe?g|png|webp|tiff?)$", href, re.I):
                continue
            if not pi:
                urn = candidate.xpath("processing-instruction('image-cloudpmc-urn')")
                if urn and urn[0].text.strip().startswith("urn:cdn:blobs/"):
                    graphic = "https://cdn.ncbi.nlm.nih.gov/pmc/" + quote(urn[0].text.strip()[len("urn:cdn:"):], safe="/")
                    break
            if pi:
                path = pi[0].text.strip()
                if path.startswith("blobs/"):
                    graphic = "https://cdn.ncbi.nlm.nih.gov/pmc/" + quote(path, safe="/")
                    break
            if media_urls is None:
                page = get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/").decode("utf-8", errors="replace")
                found_urls = re.findall(r"https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^\s\"'<>]+", page)
                media_urls = {unquote(Path(urlsplit(html.unescape(url)).path).name): html.unescape(url) for url in found_urls}
            if href in media_urls:
                graphic = media_urls[href]
                break
        if graphic is None:
            continue
        figure_title = words(caption.find("title")) or caption_text[:180]
        tags = [label for label, pattern in TYPE_PATTERNS.items() if re.search(pattern, caption_text, re.I)]
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{pmcid}-{fig_id}") + ".webp"
        results.append({
            "id": f"{pmcid}-{fig_id}", "category": category, "paper": title,
            "journal": journal, "year": year, "author": author, "doi": doi,
            "pmcid": pmcid, "label": label, "figure_title": figure_title,
            "caption": caption_text, "tags": tags, "image": (IMAGE_PATH / filename).as_posix(),
            "original": graphic,
            "paper_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/#{quote(fig_id)}",
            "doi_url": f"https://doi.org/{doi}", "license": license_url,
        })
    return results


def image_content(figure):
    url = figure["original"]
    if figure.get("figure_view") == "aip":
        from lxml import html as html_parser

        if urlsplit(url).hostname != "pubs.aip.org":
            raise ValueError(f"Unexpected AIP figure page: {url}")
        page = html_parser.fromstring(get(url))
        image_url, = page.xpath('//img[contains(concat(" ", normalize-space(@class), " "), " content-image ")]/@src')
        image = urlsplit(image_url)
        if image.scheme != "https" or image.hostname != "aipp.silverchair-cdn.com":
            raise ValueError(f"Unexpected AIP image host for {url}")
        return get(image_url)
    if not (crop := figure.get("pdf_crop")):
        return get(url)

    page = str(crop["page"])
    # Crop coordinates are in PDF points, measured from the top left.
    left, top, right, bottom = (round(point * 3) for point in crop["box"])
    with TemporaryDirectory() as directory:
        pdf = Path(directory) / "article.pdf"
        pdf.write_bytes(get(url.split("#", 1)[0]))
        return run([
            "pdftoppm", "-f", page, "-l", page, "-r", "216", "-png", "-singlefile",
            "-x", str(left), "-y", str(top), "-W", str(right - left), "-H", str(bottom - top),
            str(pdf),
        ], capture_output=True, check=True, timeout=30).stdout


def save_image(figure):
    from PIL import Image, ImageOps

    target = ROOT / figure["image"]
    if target.exists():
        try:
            with Image.open(target) as previous:
                previous.verify()
            return figure
        except OSError:
            pass
    content = image_content(figure)
    with Image.open(io.BytesIO(content)) as source:
        source.load()
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        with TemporaryDirectory(dir=target.parent) as directory:
            pending = Path(directory) / target.name
            image.save(pending, "WEBP", quality=90, method=4)
            pending.replace(target)
    return figure


def curated_figures():
    if not CURATED.exists():
        return []
    figures = []
    seen = set()
    for paper in json.loads(CURATED.read_text(encoding="utf-8")):
        metadata = {key: value for key, value in paper.items() if key not in ("source_id", "figures")}
        if metadata["category"] not in SELECTED or metadata["license"] != CC_BY:
            raise ValueError(f"Invalid topic or license for {paper['source_id']}")
        for item in paper["figures"]:
            figure_id = f"{paper['source_id']}-{item['id']}"
            if figure_id in seen or not re.fullmatch(r"[A-Za-z0-9._-]+", figure_id):
                raise ValueError(f"Invalid or duplicate figure ID: {figure_id}")
            if any(urlsplit(url).scheme != "https" for url in (
                metadata["license_evidence"], item["paper_url"], item["original"],
            )):
                raise ValueError(f"Expected HTTPS attribution and image URLs: {figure_id}")
            seen.add(figure_id)
            figures.append({
                **metadata, **item,
                "id": figure_id,
                "curated": True,
                "image": (IMAGE_PATH / f"{figure_id}.webp").as_posix(),
                "doi_url": f"https://doi.org/{metadata['doi']}",
            })
    return figures


def write_gallery_views(data):
    figures = data["figures"]
    (DATA_DIR / "figures.js").write_text(
        "window.GALLERY_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    wall_dir = DOCS_DIR / "topics"
    wall_dir.mkdir(parents=True, exist_ok=True)
    links = []
    for category in SELECTED:
        selected = [fig for fig in figures if fig["category"] == category]
        if not selected:
            continue
        filename = f"{category}.md"
        links.append((category, filename, len(selected)))
        lines = [
            f"# {category}", "", "[返回图墙索引](../index.md) · [打开网页图库](../../index.html)",
            "", f"共 {len(selected)} 张论文图例。", "",
        ]
        for fig in selected:
            title = fig["figure_title"].replace("[", "（").replace("]", "）").replace("\n", " ")
            source = " ".join(filter(None, (fig["journal"], fig.get("version"))))
            image_link = fig.get("original_label") or ("原图所在页" if fig.get("pdf_crop") else "原始图片")
            attribution = f"[{fig['paper']}]({fig['paper_url']}) · [{image_link}]({fig['original']}) · [CC BY 4.0]({fig['license']})"
            if fig.get("license_evidence"):
                attribution += f" · [许可出处]({fig['license_evidence']})"
            lines += [
                f"## {fig['label']} · {title}", "",
                f"![{fig['label']}|680](../../{fig['image']})", "",
                f"{fig['author']} · *{source}* · {fig['year']}  ",
                attribution, "",
            ]
        (wall_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    paper_count = len({fig["doi"].lower() for fig in figures})
    lines = [
        "# 类脑计算科研图谱 · 图墙", "",
        "[项目首页](../README.md) · [网页图库](../index.html) · [资源索引](resources.md)", "",
        f"{data['created']} 收录快照包含 {len(figures)} 张图例，来自 {paper_count} 篇论文。", "",
        "## 研究主题", "",
    ]
    lines += [f"- [{category}](topics/{filename}) · {count} 张" for category, filename, count in links]
    lines += [
        "", "[来源清单](../data/sources.json)记录每张图例的 DOI、图号、图注、原图链接及文章级许可。", "",
    ]
    (DOCS_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")
    write_resources(figures)
    write_local_gallery()


def resource_text(parts, as_html):
    text = []
    for part in parts:
        if isinstance(part, str):
            text.append(html.escape(part) if as_html else part)
            continue
        link = part["url"]
        if urlsplit(link).scheme != "https":
            raise ValueError(f"Expected HTTPS resource URL: {link}")
        label = part["label"]
        if as_html:
            icon = '<svg class="icon" aria-hidden="true"><use href="#icon-link"/></svg>'
            text.append(f'<a class="resource-link" href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}{icon}</a>')
        else:
            text.append(f"[{label}]({link})")
    return "".join(text)


def write_resources(figures):
    groups = json.loads((DATA_DIR / "resources.json").read_text(encoding="utf-8"))
    markdown = [
        "# 科研图片资源索引", "",
        "收录可浏览或检索科研论文图、学术图例及科研插画的网站与图集。资源类型不同，具体内容和许可请查看各自页面。", "",
        "[网页资源导航](../resources.html) · [网页图库](../index.html) · [主题图墙](index.md)", "",
    ]
    menu = []
    sections = []
    for group in groups:
        section_id = html.escape(group["id"])
        title = html.escape(group["title"])
        menu.append(f'<a href="#{section_id}">{title}</a>')
        section = [f'<section id="{section_id}" class="resource-section">', f"<h2>{title}</h2>"]
        markdown.extend([f"## {group['title']}", ""])
        if section_id == "papers":
            section.extend([
                '<div class="resource-shortcuts">',
                '<a href="index.html?journal=arXiv">图谱中的 arXiv 图件</a>',
                '<a href="index.html?journal=bioRxiv">图谱中的 bioRxiv 图件</a>',
                "</div>",
            ])
            markdown.extend([
                "[arXiv 图件](../index.html?journal=arXiv) · [bioRxiv 图件](../index.html?journal=bioRxiv)", "",
            ])
        elif section_id == "illustrations":
            markdown.extend(["本节主要收录示意插画和图标。", ""])
        markdown.extend(["| 资源 | 收录内容 |", "| --- | --- |"])
        section.append('<ul class="resource-list">')
        for row in group["rows"]:
            name, description = row["name"], row["description"]
            section.extend([
                '<li class="resource-row">',
                f'  <div class="resource-name">{resource_text(name, True)}</div>',
                f"  <p>{resource_text(description, True)}</p>",
                "</li>",
            ])
            markdown.append(f"| {resource_text(name, False)} | {resource_text(description, False)} |")
        section.extend(["</ul>", "</section>"])
        sections.append("\n".join(section))
        markdown.append("")
    menu.extend(['<a href="#topics">主题图墙</a>', '<a href="#sources">图谱资料</a>'])
    topics = []
    for category in SELECTED:
        selected = [fig for fig in figures if fig["category"] == category]
        if selected:
            thumb = html.escape(selected[0]["image"])
            topics.append(
                f'<a class="resource-theme" href="index.html?topic={quote(category)}">'
                f'<img src="{thumb}" alt="" width="70" height="44" loading="lazy">'
                f'<span>{html.escape(category)}</span><span class="topic-count">{len(selected)} 张</span></a>'
            )
    markdown.extend(["## 来源与许可", "", "外部图集和素材站中的作品许可见原始页面。[来源清单](../data/sources.json) · [选录清单](../data/curated-figures.json)", ""])
    (DOCS_DIR / "resources.md").write_text("\n".join(markdown), encoding="utf-8")
    template = Template((ROOT / "tools/resources.template.html").read_text(encoding="utf-8"))
    (ROOT / "resources.html").write_text(template.substitute(
        menu="\n          ".join(menu), sections="\n\n".join(sections), topics="\n            ".join(topics),
    ), encoding="utf-8")


def write_local_gallery():
    local_dir = ROOT / "local"
    manifest = local_dir / "sources.json"
    if not manifest.is_file():
        return

    figures = json.loads(manifest.read_text(encoding="utf-8"))["figures"]
    (local_dir / "figures.js").write_text(
        'window.GALLERY_DATA.image_prefix = "../";\n'
        "window.GALLERY_DATA.local_figures = " + json.dumps(figures, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    page = re.sub(r'((?:href|src)=")(assets/|data/|docs/)', r'\1../\2', page)
    page = page.replace('<head>', '<head>\n  <meta name="robots" content="noindex">', 1)
    gallery_script = '<script defer src="../assets/gallery.js'
    page = page.replace(gallery_script, '<script defer src="figures.js"></script>\n  ' + gallery_script, 1)
    page = page.replace('<title>类脑计算科研图谱</title>', '<title>类脑计算科研图谱 · 本地全量</title>', 1)
    page = page.replace('id="atlas-title">类脑计算科研图谱<', 'id="atlas-title">类脑计算科研图谱 · 本地全量<', 1)
    page = page.replace('href="resources.html#topics"', 'href="../resources.html#topics"', 1)
    page = page.replace('<a href="resources.html">站外资源</a>', '<a href="audit.md">素材核验记录</a>', 1)
    (local_dir / "index.html").write_text(page, encoding="utf-8")


def collect():
    (ROOT / IMAGE_PATH).mkdir(parents=True, exist_ok=True)
    jobs = [(category, pmcid) for category, ids in SELECTED.items() for pmcid in ids]
    figures = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        future_jobs = {pool.submit(article, category, pmcid): (category, pmcid) for category, pmcid in jobs}
        for future in concurrent.futures.as_completed(future_jobs):
            category, pmcid = future_jobs[future]
            try:
                found = future.result()
                figures.extend(found)
                print(f"ARTICLE {pmcid} {len(found)} figures", flush=True)
            except Exception as exc:
                failures.append({"stage": "article", "id": pmcid, "error": str(exc)})
                print(f"SKIP {pmcid}: {exc}", flush=True)

    order = {pmcid: number for number, (_, pmcid) in enumerate(jobs)}

    def figure_order(figure):
        number = re.search(r"\d+", figure["label"])
        return (
            figure["category"] != FOCUS_TOPIC,
            "extended" in figure["label"].lower(),
            int(number.group()) if number else 999,
            order[figure["pmcid"]],
        )

    figures.sort(key=figure_order)
    curated = curated_figures()
    figures = merge_curated(figures, curated)
    download_images(figures, failures)
    return write_snapshot(figures, SELECTED)


def merge_curated(existing, curated):
    return sorted(
        [*curated, *(figure for figure in existing if not figure.get("curated"))],
        key=lambda figure: figure["category"] != FOCUS_TOPIC,
    )


def download_images(figures, failures):
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        future_images = {pool.submit(save_image, fig): fig for fig in figures}
        for number, future in enumerate(concurrent.futures.as_completed(future_images), start=1):
            fig = future_images[future]
            try:
                future.result()
            except Exception as exc:
                failures.append({"stage": "image", "id": fig["id"], "error": str(exc)})
                print(f"IMAGE SKIP {fig['id']}: {exc}", flush=True)
            if number % 25 == 0 or number == len(figures):
                print(f"IMAGES {number}/{len(figures)}", flush=True)
    if failures or not figures:
        raise SystemExit(f"Collection incomplete ({len(failures)} failures); the previous snapshot was kept.")


def write_snapshot(figures, selected):
    snapshot_date = date.today().isoformat()
    data = {"created": snapshot_date, "figures": figures}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log = {
        "date": snapshot_date, "selected": selected,
        "curated_sources": sorted({fig["doi"] for fig in figures if fig.get("curated")}),
        "failures": [],
    }
    (DATA_DIR / "collection-log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--from-manifest", action="store_true", help="Rebuild the gallery and walls offline from data/sources.json.")
    modes.add_argument("--update-curated", action="store_true", help="Add the selected figures from data/curated-figures.json to the existing snapshot.")
    args = parser.parse_args()
    if args.from_manifest:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for figure in data["figures"]:
            if not (ROOT / figure["image"]).is_file():
                raise SystemExit(f"Missing preview: {figure['image']}")
    elif args.update_curated:
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))["figures"]
        recorded = json.loads((DATA_DIR / "collection-log.json").read_text(encoding="utf-8"))
        curated = curated_figures()
        download_images(curated, [])
        data = write_snapshot(merge_curated(existing, curated), recorded["selected"])
    else:
        data = collect()
    write_gallery_views(data)
    print(f"Built gallery and walls for {len(data['figures'])} figures.")


if __name__ == "__main__":
    main()
