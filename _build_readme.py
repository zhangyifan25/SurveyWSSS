#!/usr/bin/env python3
"""Build Awesome-WSSS README from main.tex + references2.bib."""
from __future__ import annotations

import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
tex = (ROOT / "main.tex").read_text(encoding="utf-8")
# Prefer references2.bib (used by main.tex); fall back to references.bib
_bib_path = ROOT / "references2.bib"
if not _bib_path.exists():
    _bib_path = ROOT / "references.bib"
bib_text = _bib_path.read_text(encoding="utf-8")


def _read_braced(s: str, start: int) -> tuple[str, int]:
    """Read a {...} value starting at index of '{'."""
    assert s[start] == "{"
    depth = 0
    i = start
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return s[start + 1 :], len(s)


def parse_bib(text: str) -> dict:
    entries = {}
    # Allow leading whitespace before @entry (some keys are indented)
    parts = re.split(r"(?=@\w+\{)", text)
    for p in parts:
        p = p.lstrip()
        m = re.match(r"@(\w+)\{([^,\s]+)\s*,", p)
        if not m:
            continue
        key = m.group(2).strip()

        def field(name: str) -> str:
            mm = re.search(rf"(?i)\b{name}\s*=\s*", p)
            if not mm:
                return ""
            i = mm.end()
            while i < len(p) and p[i].isspace():
                i += 1
            if i < len(p) and p[i] == "{":
                val, _ = _read_braced(p, i)
                return re.sub(r"\s+", " ", val).strip()
            if i < len(p) and p[i] == '"':
                j = p.find('"', i + 1)
                return re.sub(r"\s+", " ", p[i + 1 : j]).strip()
            # bare token until comma
            j = p.find(",", i)
            return re.sub(r"\s+", " ", p[i : j if j > 0 else None]).strip()

        title = field("title").replace("{", "").replace("}", "")
        year = field("year")
        venue = field("journal") or field("booktitle") or field("organization") or ""
        venue = venue.replace("{", "").replace("}", "")
        doi = field("doi")
        url = field("url")
        author = field("author")
        entries[key] = {
            "title": title,
            "year": year,
            "venue": venue,
            "doi": doi,
            "url": url,
            "author": author,
            "type": m.group(1),
        }
    return entries


bib = parse_bib(bib_text)

# Manual DOI / open-access overlays for entries missing them in the bib
KNOWN_DOI = {
    "CAM": "10.1109/CVPR.2016.319",
    "pathak2015constrained": "10.1109/ICCV.2015.209",
    "kolesnikov2016seed": "10.1007/978-3-319-46464-0_42",
    "fan2020learning": "10.1109/CVPR42600.2020.00434",
    "box2seg": "10.1007/978-3-030-58583-9_18",
    "wang2026box": "10.1109/TIP.2026.3684400",
    "yang2026diclip": "10.1109/TIP.2026.3692055",
    "CLIP": "10.48550/arXiv.2103.00020",
    "DINO": "10.1109/ICCV48922.2021.00967",
    "SAM": "10.1109/ICCV51070.2023.00371",
    "eva": "10.1016/j.imavis.2024.105171",
    "cordts2016cityscapes": "10.1109/CVPR.2016.350",
    "zamir2019isaid": "10.48550/arXiv.1905.12886",
    "han2022wsss4luad": "10.48550/arXiv.2204.06455",
    "tuxiangji12": "10.48550/arXiv.2009.12547",  # CONTA (NeurIPS'20)
    "box9": "10.48550/arXiv.2105.00957",  # SPML (ICLR'21)
}
# Non-DOI fallbacks (datasets / accepted-without-DOI)
KNOWN_URL = {
    "swissphoto2012isprs": "https://www.isprs.org/education/benchmarks/UrbanSemLab/default.aspx",
    "tuxiangji172": "https://ieeexplore.ieee.org/document/11472621",  # PLS (TMM'26)
    "qiu2026beyond": "https://cvpr.thecvf.com/virtual/2026/poster/38789",  # VDA / Qiu et al.
}
for k, doi in KNOWN_DOI.items():
    if k in bib and not bib[k].get("doi"):
        bib[k]["doi"] = doi
for k, url in KNOWN_URL.items():
    if k in bib and not bib[k].get("url") and not bib[k].get("doi"):
        bib[k]["url"] = url
# Dataset / misc venue overrides
if "swissphoto2012isprs" in bib and not (bib["swissphoto2012isprs"].get("venue") or "").strip():
    bib["swissphoto2012isprs"]["venue"] = "ISPRS Benchmark"

# Propagate DOI across duplicate titles (same paper, multiple bib keys)
_by_title: dict[str, list[str]] = defaultdict(list)
for k, e in bib.items():
    t = re.sub(r"[^a-z0-9]+", "", (e.get("title") or "").lower())
    if t:
        _by_title[t].append(k)
for keys in _by_title.values():
    if len(keys) < 2:
        continue
    doi = next((bib[k]["doi"] for k in keys if bib[k].get("doi")), "")
    url = next((bib[k]["url"] for k in keys if bib[k].get("url")), "")
    for k in keys:
        if doi and not bib[k].get("doi"):
            bib[k]["doi"] = doi
        if url and not bib[k].get("url"):
            bib[k]["url"] = url

cited: set[str] = set()
for c in re.findall(r"\\cite\{([^}]+)\}", tex):
    for k in c.split(","):
        cited.add(k.strip())

BAD_NAMES = {
    "al", "et", "the", "a", "an", "and", "or", "in", "on", "of", "to", "for",
    "with", "by", "from", "as", "is", "are", "tasks", "methods", "method",
    "computing", "mining", "graphlets", "propagation", "learning", "network",
    "framework", "model", "models", "approach", "approaches", "work", "works",
    "designs", "variants", "pipelines", "cues", "losses", "priors", "maps",
}

def looks_like_method_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 40:
        return False
    if name.lower() in BAD_NAMES:
        return False
    # CamelCase / acronym / digits / hyphen
    if re.match(r"^[A-Z][A-Za-z0-9+\-/.]*$", name):
        return True
    if re.match(r"^[A-Za-z][A-Za-z0-9+\-/.]*[0-9][A-Za-z0-9+\-/.]*$", name):
        return True
    return False

name_map: dict[str, str] = {}

# 1) Overview table names have highest priority
if True:
    tm0 = re.search(r"\\label\{tab:methods_overview\}.*?\\end\{table\*\}", tex, re.S)
    if tm0:
        for line in tm0.group(0).splitlines():
            m = re.search(r"&\s*([^&~\\]+?)(?:\$[^$]*\$)?~\\cite\{([^}]+)\}", line)
            if not m:
                continue
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            name = re.sub(r"\$.*?\$", "", name).replace("\\&", "&").strip()
            if looks_like_method_name(name) or (name and name[0].isupper()):
                for k in m.group(2).split(","):
                    name_map[k.strip()] = name

# 2) Body Name~\cite{key}
for m in re.finditer(
    r"([A-Za-z][A-Za-z0-9+\-/.]*)(?:\\textcolor\{gray\}\{\[[^\]]+\]\})?~\\cite\{([^}]+)\}",
    tex,
):
    name = m.group(1).strip(".,;: ")
    if looks_like_method_name(name):
        for k in m.group(2).split(","):
            name_map.setdefault(k.strip(), name)

# 3) Acronym from title: "STC: ..." or "FPR: ..."
def acronym_from_title(title: str) -> str:
    m = re.match(r"^([A-Za-z][A-Za-z0-9+\-]{1,20})\s*:", title.strip())
    if m and looks_like_method_name(m.group(1)):
        return m.group(1)
    return ""

# 4) First-author et al.
def author_short(author: str) -> str:
    if not author:
        return ""
    first = author.split(" and ")[0].strip()
    # "Last, First" or "First Last"
    if "," in first:
        last = first.split(",")[0].strip()
    else:
        last = first.split()[-1]
    last = re.sub(r"[^A-Za-z\-]", "", last)
    return f"{last} et al." if last else ""

code_yes: set[str] = set()
tm = re.search(r"\\label\{tab:methods_overview\}.*?\\end\{table\*\}", tex, re.S)
if tm:
    for line in tm.group(0).splitlines():
        if "\\checkmark" in line and "\\cite{" in line:
            km = re.search(r"\\cite\{([^}]+)\}", line)
            if km:
                for k in km.group(1).split(","):
                    code_yes.add(k.strip())

markers = [
    ("1.1 Seed Expansion and Adversarial Erasing", r"\\subsubsection\{Seed Expansion"),
    ("1.2 Affinity Modeling and Pseudo-Label Propagation", r"\\subsubsection\{Affinity Modeling"),
    ("1.3 Transformer Token Modeling", r"\\subsubsection\{Transformer Token"),
    ("1.4 Prototype Learning and Contrastive Representation", r"\\subsubsection\{Prototype Learning"),
    ("1.5 Background and Context Decoupling", r"\\subsubsection\{Background and Context"),
    ("1.6 Foundation-Model-Empowered Approaches", r"\\subsubsection\{Foundation-Model-Empowered"),
    ("1.7 Single-Stage Training and Pseudo-Label Denoising", r"\\subsubsection\{Single-Stage Training"),
    ("1.8 Domain-specific Image-level Variants", r"\\paragraph\{Domain-specific"),
    ("2.1 Direct Sparse Training and Consistency", r"\\subsubsection\{Direct Sparse Training"),
    ("2.2 Propagation, Region Growing, and Regularized Losses", r"\\subsubsection\{Propagation, Region Growing"),
    ("2.3 Sparse Supervision in 3D Point Clouds", r"\\subsubsection\{Sparse Supervision in 3D"),
    ("3.1 Iterative Foreground/Background Mining", r"\\subsubsection\{Iterative Foreground"),
    ("3.2 Box-Constrained Losses and Attribution", r"\\subsubsection\{Box-Constrained Losses"),
    ("3.3 Box-Prompted Foundation Models", r"\\subsubsection\{Box-Prompted Foundation"),
    ("4.1 Graph-Cut and Label Propagation", r"\\subsubsection\{Graph-Cut and Label"),
    ("4.2 Regularized and Consistency Losses", r"\\subsubsection\{Regularized and Consistency Losses\}"),
    ("4.3 Foundation-Model Scribble Segmentation", r"\\subsubsection\{Foundation-Model and Prompt-Based Scribble"),
    ("5.1 Weakly Supervised Instance Segmentation", r"\\subsubsection\{Weakly Supervised Instance"),
    ("5.2 3D Point Clouds (Cross-Cutting)", r"\\subsubsection\{3D Point Clouds\}"),
    ("5.3 Video", r"\\subsubsection\{Video\}"),
    ("6.1 Autonomous Driving", r"\\textit\{Autonomous driving"),
    ("6.2 Remote Sensing and Earth Observation", r"\\textit\{Remote sensing"),
    ("6.3 Medical Image Analysis", r"\\textit\{Medical image"),
    ("6.4 Human Parsing and Pedestrian Segmentation", r"\\textit\{Human parsing"),
]

pos_list = []
for cat, pat in markers:
    m = re.search(pat, tex)
    if m:
        pos_list.append((m.start(), cat))
pos_list.sort()
outlook_end = tex.find("\\section{Conclusion}")
meth_start = tex.find("\\section{Methodology}")

key_cat: dict[str, str] = {}
for i, (pos, cat) in enumerate(pos_list):
    end = pos_list[i + 1][0] if i + 1 < len(pos_list) else outlook_end
    for c in re.findall(r"\\cite\{([^}]+)\}", tex[pos:end]):
        for k in c.split(","):
            key_cat.setdefault(k.strip(), cat)

for k in cited:
    if k in key_cat:
        continue
    mm = re.search(rf"\\cite\{{[^}}]*\b{re.escape(k)}\b[^}}]*\}}", tex)
    idx = mm.start() if mm else -1
    if idx < 0:
        key_cat[k] = "8. Evaluation Baselines and Others"
    elif idx < meth_start:
        key_cat[k] = "7. Datasets, Metrics, and Preliminaries"
    else:
        key_cat[k] = "8. Evaluation Baselines and Others"

# Order matters: more specific patterns must come before substrings
# (e.g. CVPR before "Pattern Recognition", else CVPR→PR).
VENUE_MAP = [
    (r"Pattern Analysis and Machine Intelligence", "TPAMI"),
    (r"Transactions on Image Processing", "TIP"),
    (r"Transactions on Medical Imaging", "TMI"),
    (r"Geoscience and Remote Sensing", "TGRS"),
    (r"Circuits and Systems for Video Technology", "TCSVT"),
    (r"Transactions on Multimedia", "TMM"),
    (r"ISPRS Journal", "ISPRS"),
    (r"International Journal of Computer Vision", "IJCV"),
    (r"Computer Vision and Pattern Recognition", "CVPR"),
    (r"International Conference on Computer Vision", "ICCV"),
    (r"Computer Vision -- ECCV", "ECCV"),
    (r"European Conference on Computer Vision", "ECCV"),
    (r"Neural Information Processing Systems", "NeurIPS"),
    (r"Advances in neural information processing systems", "NeurIPS"),
    (r"AAAI Conference on Artificial Intelligence|\bAAAI\b", "AAAI"),
    (r"ACM International Conference on Multimedia", "ACM MM"),
    (r"Learning Representations", "ICLR"),
    (r"International Conference on Machine Learning|\bICML\b", "ICML"),
    (r"Selected Topics in Applied Earth", "JSTARS"),
    (r"ICASSP", "ICASSP"),
    (r"Medical Image Computing and Computer.?Assisted Intervention|\bMICCAI\b", "MICCAI"),
    (r"International Joint Conference on Artificial Intelligence|\bIJCAI\b", "IJCAI"),
    (r"Transactions on Neural Networks", "TNNLS"),
    (r"Image and Vision Computing", "IVC"),
    (r"Pattern Recognition Letters", "PRL"),
    (r"Pattern Recognition", "PR"),  # after CVPR
    (r"arXiv", "arXiv"),
]


def short_venue(v: str) -> str:
    for pat, s in VENUE_MAP:
        if re.search(pat, v, re.I):
            return s
    v2 = re.sub(r"Proceedings of the ", "", v)
    return (v2[:37] + "...") if len(v2) > 40 else (v2 or "N/A")


# Curated + commonly known WSSS code links
KNOWN_CODE = {
    "tuxiangji6": "https://github.com/jiwoon-ahn/psa",
    "tuxiangji7": "https://github.com/speedinghzl/DSRG",
    "box6": "https://github.com/YudeWang/SEAM",
    "tuxiangji42": "https://github.com/xulianuwa/MCTformer",
    "tuxiangji109": "https://github.com/xulianuwa/MCTformer",
    "tuxiangji82": "https://github.com/rulixiang/ToCo",
    "tuxiangji55": "https://github.com/EugeneLoy/SIPE",
    "tuxiangji36": "https://github.com/rulixiang/AFA",
    "tuxiangji38": "https://github.com/CVI-SZU/CLIMS",
    "tuxiangji63": "https://github.com/linyq2117/CLIP-ES",
    "tuxiangji125": "https://github.com/zbf1991/WeCLIP",
    "tuxiangji158": "https://github.com/zbf1991/WeCLIP",
    "tuxiangji119": "https://github.com/HyeokjunKweon/S2C",
    "tuxiangji136": "https://github.com/Ferenas/ExCEL",
    "tuxiangji148": "https://github.com/HalcyonZhao/POT",
    "tuxiangji12": "https://github.com/zhaozhengChen/CONTA",
    "tuxiangji67": "https://github.com/rulixiang/FPR",
    "tuxiangji84": "https://github.com/jbeomlee93/AdvCAM",
    "tuxiangji30": "https://github.com/YudeWang/NSROM",
    "tuxiangji51": "https://github.com/zhaoyang-lily/ReCAM",
    "tuxiangji43": "https://github.com/PengtaoJiang/OAA",
    "tuxiangji19": "https://github.com/jbeomlee93/ADL",
    "tuxiangji27": "https://github.com/halbielee/EPS",
    "tuxiangji65": "https://github.com/halbielee/EPS",
    "tuxiangji120": "https://github.com/SeCo-WSSS/SeCo",
    "tuxiangji103": "https://github.com/WUTCMG/DuPL",
    "tuxiangji116": "https://github.com/zwyang6/PSDPM",
    "tuxiangji140": "https://github.com/zwyang6/MoRe",
    "tuxiangji96": "https://github.com/HalcyonZhao/CTI",
    "tuxiangji179": "https://github.com/zhiwei-zhai/WeakTr",
    "box7": "https://github.com/cvlab-yonsei/BANA",
    "box5": "https://github.com/chfht/BCM",
    "box14": "https://github.com/chfht/BCM",
    "box2seg": "https://github.com/vivek7415/Box2Seg",
    "box9": "https://github.com/Twizwei/SPML",
    "box11": "https://github.com/megvii-research/TEL",
    "scribble2": "https://github.com/halbielee/CC4S",
    "scribble11": "https://github.com/halbielee/BLPSeg",
    "scribble13": "https://github.com/halbielee/ProtoSAM",
    "point7": "https://github.com/yongchengliu/DBFNet",
    "point32": "https://github.com/jsfan/TPWSSS",
    "point48": "https://github.com/bearpaw/pose-ae-train",
    "CAM": "https://github.com/zhoubolei/CAM",
    "Gradcam": "https://github.com/jacobgil/pytorch-grad-cam",
    "CLIP": "https://github.com/openai/CLIP",
    "SAM": "https://github.com/facebookresearch/segment-anything",
    "DINO": "https://github.com/facebookresearch/dino",
    "eva": "https://github.com/baaivision/EVA",
    "deeplab": "https://github.com/tensorflow/models/tree/master/research/deeplab",
    "segformer": "https://github.com/NVlabs/SegFormer",
    "DenseCRF": "https://github.com/lucasb-eyer/pydensecrf",
    "dosovitskiy2020image": "https://github.com/google-research/vision_transformer",
    "lecun1998gradient": "",
    "cordts2016cityscapes": "https://www.cityscapes-dataset.com/",
    "everingham2010pascal": "http://host.robots.ox.ac.uk/pascal/VOC/",
    "lin2014microsoft": "https://cocodataset.org/",
}


def paper_link(e: dict) -> str:
    # Prefer canonical DOI links over publisher landing URLs
    if e.get("doi"):
        return f"https://doi.org/{e['doi']}"
    if e.get("url"):
        return e["url"]
    return ""


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


# Group papers (methods + applications only; skip prelim/eval dumps)
order = [c for c, _ in markers]
groups: dict[str, list[str]] = OrderedDict((c, []) for c in order)
for k in cited:
    cat = key_cat.get(k)
    if cat in groups:
        groups[cat].append(k)

for cat in groups:
    def sort_key(k: str, _cat=cat):
        e = bib.get(k, {})
        try:
            y = int(e.get("year") or 0)
        except ValueError:
            y = 0
        return (y, name_map.get(k, k).lower())

    groups[cat] = sorted(groups[cat], key=sort_key)

n_method = sum(len(v) for v in groups.values())
n_code = sum(1 for ks in groups.values() for k in ks if KNOWN_CODE.get(k))
print(f"method/app papers={n_method} with_code={n_code}")

# Table-2 datasets (from main.tex tab:datasets_summary)
DATASETS = [
    # Domain, Dataset, Classes, Samples, Size, Supervision, homepage
    ("Natural images", "PASCAL VOC 2012", "21", "13,484", "Variable", "Image, Point, Scribble, Box", "http://host.robots.ox.ac.uk/pascal/VOC/"),
    ("Natural images", "MS COCO 2014", "81", "122,504", "Variable", "Image, Point, Box", "https://cocodataset.org/"),
    ("Natural images", "Cityscapes", "19", "5,000", "2048×1024", "Image, Point, Scribble", "https://www.cityscapes-dataset.com/"),
    ("Remote sensing", "ISPRS Potsdam", "6", "38 tiles", "6000×6000", "Image, Point", "https://www.isprs.org/education/benchmarks/UrbanSemLab/default.aspx"),
    ("Remote sensing", "ISPRS Vaihingen", "6", "33 tiles", "Variable", "Image, Point, Scribble", "https://www.isprs.org/education/benchmarks/UrbanSemLab/default.aspx"),
    ("Remote sensing", "iSAID", "16", "2,806", "Variable", "Image, Box", "https://captain-whu.github.io/iSAID/"),
    ("Medical images", "WSSS4LUAD", "3", "87 WSIs", "Variable", "Image", "https://wsss4luad.grand-challenge.org/"),
    ("Medical images", "BCSS-WSSS", "5", "31,826", "224×224", "Image", "https://bcsegmentation.grand-challenge.org/"),
    ("Medical images", "Kvasir-SEG", "2", "1,000", "Variable", "Box", "https://datasets.simula.no/kvasir-seg/"),
    ("3D point clouds", "S3DIS", "13", "271 rooms", "—", "Sparse point, 3D Box", "http://buildingparser.stanford.edu/dataset.html"),
    ("3D point clouds", "ScanNet", "20", "1,513 scans", "—", "Sparse point, 3D Box", "http://www.scan-net.org/"),
]

# --- Build README ---
lines: list[str] = []
A = lines.append

A('[![Awesome](https://cdn.rawgit.com/sindresorhus/awesome/d7305f38d29fed78fa85652e3a63e154dd8e8829/media/badge.svg)](https://github.com/sindresorhus/awesome)')
A('[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat)](../../pulls)')
A("<br />")
A('<p align="center">')
A('  <h1 align="center">A Unified Survey of Weakly Supervised Semantic Segmentation</h1>')
A('  <p align="center">')
A("    <b>Supervision Forms, Methods, and Applications</b>")
A("    <br />")
A("    <b>Submitted to IEEE TPAMI</b>")
A("    <br />")
A("    <strong>Yifan Zhang</strong>")
A("    ·")
A("    <strong>Haoying Zeng</strong>")
A("    ·")
A("    <strong>Haopeng Zhang</strong>")
A("    ·")
A("    <strong>Zhiguo Jiang</strong>")
A("    ·")
A("    <strong>Gemine Vivone</strong>")
A("  </p>")
A('  <p align="center">')
A("    <a href='./'><img src='https://img.shields.io/badge/Survey-Project-blue?style=flat' alt='Project'></a>")
A("    <a href='./'><img src='https://img.shields.io/badge/TPAMI-Submitted-orange?style=flat' alt='TPAMI'></a>")
A("  </p>")
A("</p>")
A("")
A('<p align="center"> <img src="figs/timeline.png" align="center" width="100%"> </p>')
A("")
A('**<p align="center"> Roadmap of Representative WSSS Methods (2016–2026) </p>**')
A("")
A('<p align="center"> <img src="figs/challenges.png" align="center" width="70%"> </p>')
A("")
A('**<p align="center"> Fundamental Dilemmas in WSSS </p>**')
A("")
A("This repository tracks and benchmarks weakly supervised semantic segmentation (WSSS) methods to supplement our survey:")
A("")
A("> **A Unified Survey of Weakly Supervised Semantic Segmentation: Supervision Forms, Methods, and Applications**")
A(">")
A("> Yifan Zhang, Haoying Zeng, Haopeng Zhang, Zhiguo Jiang, Gemine Vivone")
A(">")
A("> *Submitted to IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI).*")
A("")
A("**Please leave a <font color='orange'>STAR ⭐</font> if you find this project useful!**")
A("")
A("### 🔥 Highlight!!")
A("")
A("- A **unified taxonomy** of WSSS by supervision form: image-level, point, bounding box, and scribble.")
A("- Covers the full evolution from **CAM / affinity** heuristics, through **Vision Transformers**, to **foundation-model** priors (CLIP, DINO, SAM).")
A("- Summarizes **natural-image benchmarks** (PASCAL VOC, MS COCO) and **cross-domain** settings (remote sensing, medical, driving, 3D, video).")
A("- Provides **fair comparisons** on mIoU and computational footprint, plus open directions for deployment.")
A("- This repo lists papers appearing in our survey with year, venue, title/link, and code when available.")
A("")
A("# Introduction")
A("")
A("Semantic segmentation usually requires expensive pixel-level masks. **Weakly supervised semantic segmentation (WSSS)** learns dense predictions from cheaper labels such as image tags, points, boxes, or scribbles.")
A("")
A("Over the past decade, WSSS has moved from heuristic CAM expansion and affinity propagation, to Transformer token modeling, and now to foundation-model-empowered pipelines. This survey:")
A("")
A("1. Formulates a **unified mathematical view** of the four weak-label forms and multi-stage vs. single-stage training.")
A("2. Builds a **method taxonomy** primarily for 2D natural images, with extensions to instance, 3D, and video.")
A("3. Curates **datasets / metrics** and reports quantitative & qualitative comparisons.")
A("4. Reviews **applications** in driving, remote sensing, medicine, and human parsing, and outlines future prospects.")
A("")
A('<p align="center"> <img src="figs/overview.png" align="center" width="100%"> </p>')
A("")
A('**<p align="center"> Survey Paper Structure </p>**')
A("")
A('<p align="center"> <img src="figs/pipeline.png" align="center" width="100%"> </p>')
A("")
A('**<p align="center"> Training Setups in WSSS (Orthogonal to Label Forms) </p>**')
A("")
A("## Citation")
A("")
A("If you find our survey helpful, please consider citing (status: **submitted to IEEE TPAMI**):")
A("")
A("```bibtex")
A("@article{zhang2026wssssurvey,")
A("  title   = {A Unified Survey of Weakly Supervised Semantic Segmentation: Supervision Forms, Methods, and Applications},")
A("  author  = {Zhang, Yifan and Zeng, Haoying and Jiang, Zhiguo and Vivone, Gemine and Zhang, Haopeng},")
A("  year    = {2026}")
A("}")
A("```")
A("")
A("The following tables list papers discussed in the survey. **Code links are filled when known; otherwise left as N/A**.")
A("")
A("# Summary of Contents")
A("")
A("This content follows the methodology and application taxonomy of our survey.")
A("")
A("- [Introduction](#introduction)")
A("  - [Citation](#citation)")
A("- [Summary of Contents](#summary-of-contents)")
A("- [1. Image-Level Supervised Methods](#1-image-level-supervised-methods)")
A("- [2. Point-Supervised Methods](#2-point-supervised-methods)")
A("- [3. Bounding-Box-Supervised Methods](#3-bounding-box-supervised-methods)")
A("- [4. Scribble-Supervised Methods](#4-scribble-supervised-methods)")
A("- [5. Cross-Cutting Themes and Extensions](#5-cross-cutting-themes-and-extensions)")
A("  - [5.1 Weakly Supervised Instance Segmentation](#51-weakly-supervised-instance-segmentation)")
A("  - [5.2 3D Point Clouds (Cross-Cutting)](#52-3d-point-clouds-cross-cutting)")
A("  - [5.3 Video](#53-video)")
A("- [6. Applications](#6-applications)")
A("  - [6.1 Autonomous Driving](#61-autonomous-driving)")
A("  - [6.2 Remote Sensing and Earth Observation](#62-remote-sensing-and-earth-observation)")
A("  - [6.3 Medical Image Analysis](#63-medical-image-analysis)")
A("  - [6.4 Human Parsing and Pedestrian Segmentation](#64-human-parsing-and-pedestrian-segmentation)")
A("- [7. Datasets](#7-datasets)")
A("")


def emit_table(cat: str, keys: list[str]):
    A("")
    A(f"### {cat}")
    A("")
    if not keys:
        A("*No papers assigned to this subsection (or all were primarily cited elsewhere).*")
        A("")
        return
    A("| Year | Venue | Name | Paper Title / Link | Code |")
    A("| ---- | ----- | ---- | ------------------ | ---- |")
    for k in keys:
        e = bib.get(k)
        if not e:
            A(f"| - | - | `{k}` | *Missing in references.bib* | N/A |")
            continue
        year = e.get("year") or "-"
        venue = short_venue(e.get("venue") or "")
        name = name_map.get(k) or acronym_from_title(e.get("title") or "") or author_short(e.get("author") or "") or k
        name = md_escape(name)
        title = md_escape(e.get("title") or k)
        link = paper_link(e)
        if link:
            title_cell = f"[**{title}**]({link})"
        else:
            title_cell = f"**{title}**"
        code = KNOWN_CODE.get(k, "")
        code_cell = f"[Code]({code})" if code else "N/A"
        A(f"| {year} | {venue} | {name} | {title_cell} | {code_cell} |")
    A("")


def merge_keys(prefix: str) -> list:
    keys = []
    seen = set()
    for cat in order:
        if cat.startswith(prefix):
            for k in groups.get(cat, []):
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
    def sort_key(k: str):
        e = bib.get(k, {})
        try:
            y = int(e.get("year") or 0)
        except ValueError:
            y = 0
        name = name_map.get(k) or acronym_from_title(e.get("title") or "") or author_short(e.get("author") or "") or k
        return (y, name.lower())
    return sorted(keys, key=sort_key)

def emit_merged(title: str, blurb: str, prefix: str):
    A("")
    A(f"# {title}")
    A("")
    A(blurb)
    keys = merge_keys(prefix)
    A("")
    if not keys:
        A("*No papers in this section.*")
        A("")
        return
    A("| Year | Venue | Name | Paper Title / Link | Code |")
    A("| ---- | ----- | ---- | ------------------ | ---- |")
    for k in keys:
        e = bib.get(k)
        if not e:
            A(f"| - | - | `{k}` | *Missing in references.bib* | N/A |")
            continue
        year = e.get("year") or "-"
        venue = short_venue(e.get("venue") or "")
        name = name_map.get(k) or acronym_from_title(e.get("title") or "") or author_short(e.get("author") or "") or k
        name = md_escape(name)
        title_ = md_escape(e.get("title") or k)
        link = paper_link(e)
        title_cell = f"[**{title_}**]({link})" if link else f"**{title_}**"
        code = KNOWN_CODE.get(k, "")
        code_cell = f"[Code]({code})" if code else "N/A"
        A(f"| {year} | {venue} | {name} | {title_cell} | {code_cell} |")
    A("")

# Parent headers (sections 1-4 merged; 5-6 keep subsections)
A("")
emit_merged(
    "1. Image-Level Supervised Methods",
    "Image-level labels only indicate class presence. Methods invent spatial supervision via CAM expansion, affinity propagation, Transformer tokens, prototypes, background decoupling, foundation-model priors, and single-stage training.",
    "1.",
)
emit_merged(
    "2. Point-Supervised Methods",
    "Sparse clicks provide a nonempty pixel set. Emphasis shifts to growing clicks and regularizing unlabeled regions (including 3D clouds).",
    "2.",
)
emit_merged(
    "3. Bounding-Box-Supervised Methods",
    "Boxes give coarse extent but mixed interiors. Methods mine latent masks, impose box-consistent losses, or use boxes as foundation-model prompts.",
    "3.",
)
emit_merged(
    "4. Scribble-Supervised Methods",
    "Scribbles provide sparse strokes (and optional background). Pipelines combine graph-cut / random-walk propagation with regularized losses and foundation prompts.",
    "4.",
)

A("# 5. Cross-Cutting Themes and Extensions")
A("")
A("Beyond static 2D semantic segmentation: instance segmentation, 3D clouds, and video.")
for cat in order:
    if cat.startswith("5."):
        emit_table(cat, groups.get(cat, []))

A("# 6. Applications")
A("")
A("Where weak labels matter most outside object-centric VOC/COCO.")
for cat in order:
    if cat.startswith("6."):
        emit_table(cat, groups.get(cat, []))

A("# 7. Datasets")
A("")
A("Representative datasets used in our survey (Table II of the paper).")
A("")
A("| Domain | Dataset | Classes | Samples | Image size | Supervision | Link |")
A("| ------ | ------- | ------- | ------- | ---------- | ----------- | ---- |")
for domain, name, ncls, nsamp, size, superv, link in DATASETS:
    A(f"| {domain} | **{name}** | {ncls} | {nsamp} | {size} | {superv} | [Link]({link}) |")
A("")

readme_path = OUT / "README.md"
readme_path.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", readme_path, "lines", len(lines))

meta = {
    "n_method": n_method,
    "n_code": n_code,
    "groups": {c: groups[c] for c in order},
    "datasets": DATASETS,
}
(OUT / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("Wrote _meta.json")
