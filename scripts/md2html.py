#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xyb-md2html —— 把 Markdown 转成小胰宝社区品牌化 HTML（PDF 的上游产物）。

设计要点
1. 原文零改写：只做结构转换与样式注入，不改动、不增删任何正文文字。
2. 品牌令牌集中在 BRAND 里，禁止在别处硬编码颜色。
3. 只依赖 python-markdown；若环境缺失则回落到内置轻量转换器，保证不因缺库中断。

CLI:
    python md2html.py input.md [-o output.html] [--title T] [--subtitle S]
                        [--brand 小胰宝社区] [--ip-notice "..."] [--mode report|plain]
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------------
# 品牌令牌（小胰宝 v2.0 令牌；与 xyb-ppt-template 链路 B 同源，勿混用链路 A 色板）
# ----------------------------------------------------------------------------
BRAND: dict[str, str] = {
    "mint": "#299D8C",
    "mint_deep": "#1F7A6E",
    "ink": "#213139",
    "body": "#48565A",
    "light": "#EDF6F3",
    "light_soft": "#F5FAF9",
    "line": "#D8E6E2",
    "muted": "#7C8B8F",
    "warm": "#C4632D",       # 警示/缺口（仅少量使用）
    "warm_bg": "#FBF6EE",
}

BRAND_NAME = "小胰宝社区"
BRAND_SUB = "XIAOYIBAO COMMUNITY ｜ 胰腺癌患者与家属互助社区"

# IP 归属默认文案（可由 --ip-notice 覆盖）
IP_NOTICE_DEFAULT = (
    "本文件由小胰宝社区维护整理并发布。除标注来源的第三方内容外，"
    "本文件的整理、编排与呈现版权归小胰宝社区（XiaoYiBao Community）所有。"
    "本文件仅用于社区内部学习与信息共享，不构成医疗建议、诊疗依据或投资建议，"
    "不得用于商业用途；第三方内容的版权归原作者及原机构所有。"
)

# 关键词 → 状态标签样式
PILL_MAP: dict[str, str] = {
    "已核实": "ok", "已确认": "ok",
    "待核实": "pend", "未核实": "pend", "未披露": "pend",
    "未执行": "pend", "未支持": "pend", "未访问": "pend",
    "首次基线": "base", "基线": "base",
    "外部": "ext",
}

FONT_STACK = ('"Helvetica Neue","PingFang SC","Hiragino Sans GB",'
              '"Noto Sans CJK SC","Source Han Sans SC",sans-serif')


# ----------------------------------------------------------------------------
# Markdown 解析辅助
# ----------------------------------------------------------------------------
def extract_title(md: str) -> tuple[str, int]:
    """取第一个一级标题作为文档标题，返回 (标题, 行号)；无则返回 ('', -1)。"""
    for i, line in enumerate(md.splitlines()):
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip(), i
    return "", -1


def extract_meta(md: str, skip_lines: set[int]) -> tuple[list[tuple[str, str]], set[int]]:
    """抽取文档头部形如 `**键**：值` 的元信息行，返回 (items, 已消费行号)。"""
    items: list[tuple[str, str]] = []
    used: set[int] = set()
    stopped = False
    for i, line in enumerate(md.splitlines()):
        if i in skip_lines:
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith("---") or s.startswith("## "):
            stopped = True
        if stopped:
            continue
        m = re.match(r"^\*\*(?P<k>[^*]+)\*\*\s*[:：]\s*(?P<v>.+)$", s)
        if m:
            key = m.group("k").strip()
            val = re.sub(r"\*\*", "", m.group("v")).strip()
            if len(key) <= 12 and len(val) <= 120:
                items.append((key, val))
                used.add(i)
        elif not s.startswith("#"):
            # 头部出现普通段落即停止抽取，避免误吞正文
            if items:
                break
    return items, used


def strip_meta_lines(md: str, used: set[int]) -> str:
    if not used:
        return md
    return "\n".join(l for i, l in enumerate(md.splitlines()) if i not in used)


def normalize_lists(md: str) -> str:
    """把 2 空格缩进的子列表补成 4 空格，避免 python-markdown 把它当成续行。"""
    out = []
    for line in md.splitlines():
        m = re.match(r"^( +)([-*+] |\d+\. )", line)
        if m and len(m.group(1)) % 4 != 0:
            indent = " " * ((len(m.group(1)) // 4 + 1) * 4)
            line = indent + line[len(m.group(1)):]
        out.append(line)
    return "\n".join(out)


def md_to_html_body(md: str) -> str:
    """Markdown → HTML 片段。优先 python-markdown，缺失时回落内置转换器。"""
    try:
        import markdown  # type: ignore

        return markdown.markdown(
            md,
            extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
            output_format="html5",
        )
    except Exception:
        return _fallback_md(md)


def _fallback_md(md: str) -> str:
    """内置轻量转换器：标题/列表/表格/引用/分隔线/段落 + 行内样式。"""
    def inline(t: str) -> str:
        t = html.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        return t

    lines = md.splitlines()
    out: list[str] = []
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s:
            flush()
            i += 1
            continue
        if re.fullmatch(r"-{3,}|\*{3,}", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^(#{1,6}) (.+)$", s)
        if m:
            flush()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        # 表格
        if "|" in s and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            flush()
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        # 引用
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>")
            continue
        # 列表
        if re.match(r"^([-*+]|\d+\.)\s", s):
            flush()
            ordered = bool(re.match(r"^\d+\.\s", s))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+\.)\s", lines[i]):
                content = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i])
                # 续行归并
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(
                    r"^\s*([-*+]|\d+\.)\s", lines[i]
                ) and not lines[i].startswith("#") and "|" not in lines[i]:
                    content += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(content)}</li>")
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


# ----------------------------------------------------------------------------
# HTML 后处理（只做样式注入，不动文字）
# ----------------------------------------------------------------------------
_URL_RE = re.compile(r"https?://[^\s<>\u4e00-\u9fff）)；;、，。】》\"']+")
_TAG_RE = re.compile(r"(<[^>]+>)")


def linkify(html_text: str) -> str:
    """把裸 URL 变成链接；跳过标签内部与已有 a 标签内容。"""
    parts = _TAG_RE.split(html_text)
    inside_a = False
    for idx, seg in enumerate(parts):
        if _TAG_RE.fullmatch(seg):
            if seg.lower().startswith("<a"):
                inside_a = True
            elif seg.lower().startswith("</a"):
                inside_a = False
            continue
        if inside_a or "http" not in seg:
            continue
        parts[idx] = _URL_RE.sub(
            lambda m: f'<a class="url" href="{m.group(0)}">{m.group(0)}</a>', seg
        )
    return "".join(parts)


def pills(html_text: str) -> str:
    """把状态词渲染成标签。

    两种命中方式：
    1) 独立成词的加粗词：`**已核实**`
    2) 整格只有状态词（可带一段括注）的表格单元格：`| 待核实（付费墙） |`
       —— 监测日报的「证据状态」列大多没有加粗，靠这条兜住。
    """
    def repl_strong(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        key = re.split(r"[（(]", inner)[0].strip()
        cls = PILL_MAP.get(key)
        if not cls:
            return m.group(0)
        return f'<span class="pill {cls}">{html.escape(inner)}</span>'

    html_text = re.sub(r"<strong>([^<]{1,30})</strong>", repl_strong, html_text)

    keys = "|".join(sorted(PILL_MAP, key=len, reverse=True))
    cell_re = re.compile(r"<td>([^<]{1,90})</td>")
    status_re = re.compile(rf"^({keys})(（[^）]{{0,60}}）)?$")

    def repl_td(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        hit = status_re.match(inner)
        if not hit:
            return m.group(0)
        key, paren = hit.group(1), hit.group(2) or ""
        return f'<td><span class="pill {PILL_MAP[key]}">{html.escape(key)}</span>{paren}</td>'

    return cell_re.sub(repl_td, html_text)


def tag_wide_tables(html_text: str) -> str:
    """列数多的表格加 class，便于 CSS 自动缩字号。"""
    def repl(m: re.Match[str]) -> str:
        cols = m.group(0).count("<th")
        cls = "tbl w7" if cols >= 7 else ("tbl w6" if cols >= 6 else "tbl")
        return f'<table class="{cls}">'

    return re.sub(r"<table>", repl, html_text)


# 只匹配「内部不含嵌套列表」的扁平列表，避免误伤 <li> 里的子列表
_FLAT_LIST_RE = re.compile(r"<(ul|ol)>((?:(?!</?[uo]l[ >]).)*?)</\1>", re.S)


def keep_short_lists(html_text: str, max_items: int = 4, max_chars: int = 400) -> str:
    """小列表整块不跨页。

    动机：监测日报收尾时，一个 3~4 行的小列表常被挤到页脚边上，视觉上"贴"在页脚。
    规则：条目 ≤ max_items 且正文 ≤ max_chars 的扁平列表加 class="keep"，
    由 CSS `break-inside: avoid` 整块推到下一页——放不下就整体换页，不硬塞。
    阈值刻意收得较紧：只保护"小块"，长列表仍允许自然分页，避免为长文档
    撑出一页只剩版权声明的孤页（实测 6/700 会，4/400 不会）。
    """
    def repl(m: re.Match[str]) -> str:
        tag, inner = m.group(1), m.group(2)
        items = len(re.findall(r"<li>", inner))
        chars = len(re.sub(r"<[^>]+>", "", inner))
        if items <= max_items and chars <= max_chars:
            return f'<{tag} class="keep">{inner}</{tag}>'
        return m.group(0)

    return _FLAT_LIST_RE.sub(repl, html_text)


def wrap_tables(html_text: str) -> str:
    """Wrap Markdown tables so narrow screens can scroll without squeezing columns."""
    table_re = re.compile(r'<table class="tbl(?: w[67])?">.*?</table>', re.S)
    return table_re.sub(lambda m: f'<div class="tbl-wrap">{m.group(0)}</div>', html_text)


def postprocess(html_text: str) -> str:
    return wrap_tables(keep_short_lists(tag_wide_tables(pills(linkify(html_text)))))


# ----------------------------------------------------------------------------
# 样式
# ----------------------------------------------------------------------------
def css() -> str:
    b = BRAND
    return f"""
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
body{{font-family:{FONT_STACK};font-size:9.5pt;line-height:1.8;color:{b['body']};background:#fff;}}
.hero{{background:linear-gradient(135deg,{b['light']} 0%,{b['light_soft']} 60%,#FFFFFF 100%);
  border:1px solid {b['line']};border-radius:4mm;padding:7mm 7mm 6mm;margin-bottom:6mm;break-inside:avoid;}}
.hero-top{{display:flex;align-items:center;gap:4mm;margin-bottom:5mm;}}
.hero-logo{{width:22mm;height:22mm;object-fit:contain;flex:0 0 auto;}}
.hero-logo.photo{{border-radius:4.5mm;border:1px solid {b['line']};background:#fff;object-fit:cover;}}
.hero-brand{{flex:1;min-width:0;}}
.brand-name{{font-size:14pt;font-weight:700;color:{b['ink']};letter-spacing:.5pt;}}
.brand-name .dot{{color:{b['mint']};}}
.brand-sub{{font-size:7.5pt;color:{b['muted']};letter-spacing:.6pt;margin-top:.6mm;}}
.hero-tag{{text-align:center;font-size:8.5pt;font-weight:700;color:#fff;background:{b['mint']};
  border-radius:2.5mm;padding:2mm 4mm;line-height:1.35;letter-spacing:1pt;}}
.hero-tag small{{display:block;font-size:6pt;font-weight:400;letter-spacing:1.5pt;opacity:.85;}}
h1.doc-title{{font-size:17.5pt;font-weight:700;color:{b['ink']};line-height:1.35;margin-bottom:1.5mm;}}
.doc-sub{{font-size:9.5pt;color:{b['mint_deep']};font-weight:600;margin-bottom:4mm;}}
.hero-meta{{display:flex;flex-wrap:wrap;gap:2mm;}}
.meta-item{{background:#fff;border:1px solid {b['line']};border-radius:2mm;padding:1.6mm 3mm;
  font-size:7.6pt;line-height:1.45;max-width:100%;}}
.meta-label{{color:{b['muted']};margin-right:1.5mm;}}
.meta-value{{color:{b['ink']};font-weight:600;}}
/* 正文 */
.content h2{{font-size:12.5pt;font-weight:700;color:{b['ink']};border-left:1.6mm solid {b['mint']};
  padding-left:2.8mm;margin:8mm 0 4mm;line-height:1.5;break-after:avoid;page-break-after:avoid;}}
.content h3{{font-size:10pt;font-weight:700;color:{b['mint_deep']};margin:5mm 0 2.5mm;line-height:1.5;break-after:avoid;page-break-after:avoid;}}
.content h4{{font-size:9.4pt;font-weight:700;color:{b['ink']};margin:4mm 0 2mm;line-height:1.5;break-after:avoid;page-break-after:avoid;}}
.content p{{margin-bottom:3mm;}}
.content strong,.content b{{color:{b['ink']};font-weight:700;}}
.content a{{color:{b['mint_deep']};text-decoration:none;overflow-wrap:anywhere;}}
.content hr{{border:none;border-top:.4mm solid {b['line']};margin:5mm 0;}}
.content ul{{list-style:none;margin-bottom:2mm;}}
.content ul li{{position:relative;padding-left:4.5mm;margin-bottom:2.5mm;}}
.content ul li::before{{content:"";position:absolute;left:.8mm;top:1.6mm;width:1.6mm;height:1.6mm;
  border-radius:50%;background:{b['mint']};}}
.content ul ul li::before{{background:#9CC9C1;width:1.3mm;height:1.3mm;}}
.content ol{{margin:0 0 2mm 5mm;}}
.content ol li{{margin-bottom:2.5mm;padding-left:.5mm;}}
.content ol li::marker{{color:{b['mint_deep']};font-weight:700;}}
.content blockquote{{background:{b['light']};border-radius:2.5mm;padding:3mm 3.5mm;margin:2.5mm 0;
  break-inside:avoid;}}
.content blockquote p{{margin:0;}}
.content code{{font-family:"SF Mono",Menlo,Consolas,monospace;font-size:8pt;
  background:{b['light_soft']};border-radius:1mm;padding:.2mm 1mm;}}
.content pre{{background:{b['light_soft']};border:1px solid {b['line']};border-radius:2mm;
  padding:3mm;font-size:7.8pt;overflow:hidden;white-space:pre-wrap;word-break:break-all;margin-bottom:2.5mm;}}
.content pre code{{background:none;padding:0;}}
/* 表格 */
.tbl-wrap{{margin:3mm 0 4mm;overflow-x:auto;}}
table.tbl{{width:100%;border-collapse:collapse;font-size:8pt;line-height:1.7;
  border:1px solid {b['line']};}}
table.tbl.w6{{font-size:7.6pt;}}
table.tbl.w7{{font-size:7pt;}}
table.tbl thead th{{background:{b['mint']};color:#fff;font-weight:700;text-align:left;
  padding:2.5mm 2mm;font-size:.96em;white-space:normal;}}
/* 首列多为短标签（主题/字段名）：收窄到内容宽，把宽度让给长文本列 */
table.tbl thead th:first-child{{width:14mm;min-width:14mm;}}
table.tbl tbody td:first-child{{white-space:normal;min-width:14mm;}}
table.tbl tbody td{{padding:2.5mm 2mm;vertical-align:top;border-top:.3mm solid {b['line']};overflow-wrap:anywhere;}}
table.tbl tbody tr:nth-child(even){{background:{b['light_soft']};}}
table.tbl tbody tr{{break-inside:avoid;}}
table.tbl a.url{{word-break:break-all;font-size:.92em;}}
/* 状态标签 */
.pill{{display:inline-block;font-size:.86em;font-weight:600;border-radius:6mm;
  padding:.3mm 2mm;margin-right:1mm;letter-spacing:.3pt;white-space:nowrap;}}
.pill.ok{{background:{b['mint']};color:#fff;}}
.pill.pend{{background:#fff;border:.35mm solid {b['mint']};color:{b['mint_deep']};}}
.pill.base{{background:{b['ink']};color:#fff;}}
.pill.ext{{background:#E8EEF0;color:#5A6B70;}}
.content ul.keep,.content ol.keep{{break-inside:avoid;}}
.content p,.content li{{orphans:3;widows:3;}}
.content p{{break-inside:avoid-page;page-break-inside:avoid;}}
.content h2,.content h3,.content h4{{break-after:avoid-page;}}
.page-break{{break-before:page;page-break-before:always;height:0;}}
.content pre{{break-inside:avoid;}}
/* 尾注（版权页） */
.endnote{{margin-top:4mm;border-top:.6mm solid {b['mint']};padding-top:2mm;
  font-size:7.5pt;color:{b['muted']};line-height:1.55;break-inside:avoid;}}
.endnote .ip{{color:{b['mint_deep']};font-weight:700;}}
.endnote p{{margin-bottom:1.5mm;}}
@page{{margin:16mm 18mm 18mm;}}
@media screen{{
  body{{max-width:1020px;margin:0 auto;padding:36px 48px;}}
  .tbl-wrap{{overscroll-behavior-x:contain;}}
}}
@media screen and (max-width:700px){{
  body{{padding:22px 18px;font-size:10pt;}}
  .hero{{padding:6mm;margin-bottom:7mm;}}
  .hero-top{{flex-wrap:wrap;gap:3mm;}}
  .hero-logo{{width:18mm;height:18mm;}}
  .hero-brand{{flex:1 1 60%;}}
  .brand-sub{{letter-spacing:0;}}
  .hero-tag{{margin-left:auto;}}
  h1.doc-title{{font-size:16pt;}}
  .content h2{{font-size:12pt;}}
  table.tbl{{min-width:560px;}}
}}
@media print{{
  body{{max-width:none;margin:0;padding:0;}}
  .tbl-wrap{{overflow:visible;}}
  .page-break{{break-before:page;page-break-before:always;}}
  .content h2,.content h3,.content h4{{break-after:avoid-page;page-break-after:avoid;}}
  .content p{{break-inside:avoid-page;page-break-inside:avoid;orphans:3;widows:3;}}
  .content blockquote,.content ul.keep,.content ol.keep,.content pre,.endnote{{break-inside:avoid-page;page-break-inside:avoid;}}
  table.tbl thead{{display:table-header-group;}}
  table.tbl tbody tr{{break-inside:avoid-page;page-break-inside:avoid;}}
}}
.doc-info{{background:{b['light_soft']};border:1px solid {b['line']};border-radius:2mm;
  padding:2mm 3mm;margin:1.6mm 0;font-size:7.2pt;display:flex;flex-wrap:wrap;}}
.di-row{{flex:0 0 47%;padding:.4mm 0;display:flex;gap:2mm;}}
.di-k{{flex:0 0 14mm;color:{b['muted']};}}
.di-v{{color:{b['ink']};font-weight:600;}}
.endnote .meta-line{{font-size:7pt;color:#93A1A4;}}
"""


def logo_data_uri(path: Path) -> str:
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(path.suffix.lower().lstrip("."), "image/png")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build_document(
    md_text: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    brand: str = BRAND_NAME,
    brand_sub: str = BRAND_SUB,
    ip_notice: str = IP_NOTICE_DEFAULT,
    logo_path: Path | None = None,
    mode: str = "report",
    source_name: str = "",
    generated_at: str = "",
    tag: str = "文档",
) -> dict[str, Any]:
    """生成完整 HTML 文档；返回 {html, title, meta, ip_notice, brand}。"""
    md_text = md_text.replace("\r\n", "\n")
    auto_title, title_line = extract_title(md_text)
    skip = {title_line} if title_line >= 0 else set()
    meta_items, used = extract_meta(md_text, skip)
    body_md = strip_meta_lines(md_text, used | skip)
    body_md = normalize_lists(body_md)
    body_html = postprocess(md_to_html_body(body_md))

    doc_title = title or auto_title or (source_name or "未命名文档")
    doc_sub = subtitle or ""

    if mode == "plain":
        hero = (
            f'<header class="plain-head">'
            f'<h1 class="doc-title">{html.escape(doc_title)}</h1>'
            + (f'<div class="doc-sub">{html.escape(doc_sub)}</div>' if doc_sub else "")
            + "</header>"
        )
    else:
        logo_html = ""
        if logo_path and logo_path.exists():
            cls = "hero-logo photo" if logo_path.suffix.lower() in (".jpg", ".jpeg") else "hero-logo"
            logo_html = f'<img class="{cls}" src="{logo_data_uri(logo_path)}" alt="{html.escape(brand)} Logo">'
        chips = "".join(
            f'<div class="meta-item"><span class="meta-label">{html.escape(k)}</span>'
            f'<span class="meta-value">{html.escape(v)}</span></div>'
            for k, v in meta_items
        )
        hero = (
            f'<header class="hero">'
            f'<div class="hero-top">{logo_html}'
            f'<div class="hero-brand"><div class="brand-name">{html.escape(brand)}'
            f'<span class="dot"> · </span>维护出品</div>'
            f'<div class="brand-sub">{html.escape(brand_sub)}</div></div>'
            f'<div class="hero-tag">{html.escape(tag)}<small>XIAOYIBAO COMMUNITY</small></div>'
            f"</div>"
            f'<h1 class="doc-title">{html.escape(doc_title)}</h1>'
            + (f'<div class="doc-sub">{html.escape(doc_sub)}</div>' if doc_sub else "")
            + (f'<div class="hero-meta">{chips}</div>' if chips else "")
            + "</header>"
        )

    src_line = f"原始文档：{html.escape(source_name)}" if source_name else ""
    gen_line = f"生成时间：{html.escape(generated_at)}" if generated_at else ""
    endnote = (
        f'<div class="endnote">'
        f'<p><span class="ip">{html.escape(brand)}维护出品</span> — '
        f"{html.escape(ip_notice)}</p>"
        f'<div class="doc-info">'
        + (f'<div class="di-row"><span class="di-k">原始文档</span><span class="di-v">{html.escape(source_name)}</span></div>' if source_name else "")
        + (f'<div class="di-row"><span class="di-k">生成时间</span><span class="di-v">{html.escape(generated_at)}</span></div>' if generated_at else "")
        + f'<div class="di-row"><span class="di-k">生成链路</span><span class="di-v">xyb-md2pdf v1.1.0 ｜ {html.escape(brand)}品牌模板</span></div>'
        + f'<div class="di-row"><span class="di-k">文档状态</span><span class="di-v">只读 PDF（允许阅读与打印，禁止修改、注释与复制）</span></div>'
        + f"</div>"
        f'<p class="meta-line">如需勘误、补充线索或申请转载，请联系{html.escape(brand)}维护组。</p>'
        f"</div>"
    )

    doc = (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(doc_title)} · {html.escape(brand)}</title>"
        f"<style>{css()}</style></head><body>"
        f"{hero}<article class=\"content\">{body_html}</article>{endnote}"
        "</body></html>"
    )
    return {
        "html": doc, "title": doc_title, "meta": meta_items,
        "ip_notice": ip_notice, "brand": brand, "subtitle": doc_sub,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown → 小胰宝社区品牌化 HTML")
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--title")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--brand", default=BRAND_NAME)
    ap.add_argument("--ip-notice", default=IP_NOTICE_DEFAULT)
    ap.add_argument("--logo")
    ap.add_argument("--mode", choices=["report", "plain"], default="report")
    args = ap.parse_args()

    src = Path(args.input)
    out = Path(args.output) if args.output else src.with_suffix(".html")
    doc = build_document(
        src.read_text(encoding="utf-8"),
        title=args.title, subtitle=args.subtitle, brand=args.brand,
        ip_notice=args.ip_notice,
        logo_path=Path(args.logo) if args.logo else None,
        mode=args.mode, source_name=src.name,
    )
    out.write_text(doc["html"], encoding="utf-8")
    print(f"HTML: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
