#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xyb-md2pdf —— Markdown → 小胰宝社区品牌 PDF（原文 + logo + IP 归属 + 默认只读）

链路：Markdown 原文 → 品牌化 HTML（md2html.py）→ Chrome/Playwright 打印 PDF
      → pypdf 施加只读权限与文档元数据 → 文件系统置为只读(0444)

用法示例：
    python md2pdf.py report.md
    python md2pdf.py report.md -o out.pdf --title "自定义标题" --tag 监测日报
    python md2pdf.py report.md --no-readonly --allow-copy --html

只读语义（默认开启）：
    · 文档权限：允许阅读/打印，禁止修改、注释、表单填写、拼装；默认亦禁止复制文字
      （需要允许复制时加 --allow-copy）
    · 文件权限：输出文件 chmod 0444，重复生成时脚本会先自行解锁再写回
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
sys.path.insert(0, str(HERE))

import md2html  # noqa: E402
from md2html import BRAND_NAME, IP_NOTICE_DEFAULT  # noqa: E402

DEFAULT_LOGO = SKILL_DIR / "assets" / "xyb-mascot.png"
DEFAULT_OWNER_PW = "xyb-community"
FONT = "'PingFang SC','Helvetica Neue',sans-serif"


# ----------------------------------------------------------------------------
# 页眉 / 页脚模板（Chrome 打印模板，每页重复）
# ----------------------------------------------------------------------------
def header_template(brand: str, title: str, logo_uri: str, right_text: str) -> str:
    logo = ""
    if logo_uri:
        logo = (f'<img src="{logo_uri}" style="height:7mm;width:7mm;object-fit:contain;'
                f'margin-right:2.5mm;">')
    safe_title = title if len(title) <= 42 else title[:41] + "…"
    return f"""
<div style="width:100%;box-sizing:border-box;padding:0 18mm;font-family:{FONT};
     font-size:8px;color:#48565A;border-bottom:0.4mm solid #299D8C;height:11mm;">
  <div style="display:flex;align-items:center;justify-content:space-between;height:100%;">
    <div style="display:flex;align-items:center;overflow:hidden;">
      {logo}
      <span style="color:#299D8C;font-weight:700;font-size:9px;letter-spacing:0.5px;
            white-space:nowrap;">{brand}</span>
      <span style="color:#D8E6E2;margin:0 2.5mm;">｜</span>
      <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{safe_title}</span>
    </div>
    <div style="color:#7C8B8F;white-space:nowrap;">{right_text}</div>
  </div>
</div>
"""


def footer_template(brand: str) -> str:
    return f"""
<div style="width:100%;box-sizing:border-box;padding:0 18mm;font-family:{FONT};
     font-size:7.5px;color:#7C8B8F;border-top:0.4mm solid #299D8C;height:9mm;">
  <div style="display:flex;align-items:center;justify-content:space-between;height:100%;">
    <div>
      <span style="color:#299D8C;font-weight:700;">{brand}维护</span>
      <span style="color:#D8E6E2;margin:0 2mm;">｜</span>
      © {datetime.now().year} {brand} · 版权归{brand}所有
      <span style="color:#D8E6E2;margin:0 2mm;">｜</span>
      不构成医疗或投资建议
    </div>
    <div>第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页</div>
  </div>
</div>
"""


# ----------------------------------------------------------------------------
# 渲染
# ----------------------------------------------------------------------------
def launch_browser(pw):
    """优先用本机 Chrome，失败则回落 Playwright 自带 Chromium。"""
    last = None
    for kwargs in ({"channel": "chrome"}, {}):
        try:
            return pw.chromium.launch(headless=True, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"无法启动浏览器: {last}")


def render_pdf(html_path: Path, pdf_path: Path, header: str, footer: str,
               paper: str, landscape: bool) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = launch_browser(pw)
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state("load")
        page.wait_for_timeout(600)  # 等内嵌图片/字体就绪
        page.pdf(
            path=str(pdf_path),
            format=paper,
            landscape=landscape,
            print_background=True,
            display_header_footer=True,
            header_template=header,
            footer_template=footer,
            margin={"top": "16mm", "bottom": "18mm", "left": "18mm", "right": "18mm"},
        )
        browser.close()


# ----------------------------------------------------------------------------
# 只读处理
# ----------------------------------------------------------------------------
def aes_available() -> bool:
    """AES 加密依赖 cryptography；缺失时降级到 RC4-128，仍可施加只读权限。"""
    try:
        import cryptography  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def apply_readonly(pdf_path: Path, *, title: str, subject: str,
                   allow_copy: bool, owner_password: str) -> dict:
    """为 PDF 写入元数据并施加只读权限（禁改/禁注释；默认亦禁复制）。"""
    from pypdf import PdfWriter
    from pypdf.constants import UserAccessPermissions as P

    flags = P.PRINT | P.PRINT_TO_REPRESENTATION
    if allow_copy:
        flags |= P.EXTRACT_TEXT_AND_GRAPHICS

    metadata = {
        "/Title": title,
        "/Author": BRAND_NAME,
        "/Subject": subject,
        "/Creator": f"{BRAND_NAME} xyb-md2pdf",
        "/Producer": f"{BRAND_NAME} xyb-md2pdf",
        "/Keywords": f"{BRAND_NAME}, 版权归{BRAND_NAME}所有, 只读文档",
    }
    tmp = pdf_path.with_suffix(".ro.pdf")
    algo = "AES-256" if aes_available() else None
    last: Exception | None = None
    for attempt_algo in (algo, None):  # 先试 AES-256，失败则退回默认（RC4-128）
        writer = PdfWriter(clone_from=str(pdf_path))
        try:
            writer.add_metadata(metadata)
            kwargs = {"permissions_flag": flags}
            if attempt_algo:
                kwargs["algorithm"] = attempt_algo
            writer.encrypt(user_password="", owner_password=owner_password, **kwargs)
            with open(tmp, "wb") as fh:
                writer.write(fh)
            os.replace(tmp, pdf_path)
            last = None
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            if tmp.exists():
                tmp.unlink()
        finally:
            writer.close()
    if last is not None:
        raise RuntimeError(f"施加只读权限失败：{last}")

    # 复核（IntFlag 必须用位与判断，直接取属性恒为真）
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    perms = reader.user_access_permissions
    return {
        "encrypted": bool(reader.is_encrypted),
        "algorithm": "AES-256" if algo else "RC4-128",
        "can_print": bool(perms & P.PRINT) if perms is not None else None,
        "can_modify": bool(perms & P.MODIFY) if perms is not None else None,
        "can_copy": bool(perms & P.EXTRACT_TEXT_AND_GRAPHICS) if perms is not None else None,
        "raw_p": int(perms) if perms is not None else None,
    }


def set_file_readonly(path: Path, readonly: bool) -> str:
    """把输出文件置为只读 / 可写；写回前先解锁，避免二次运行失败。"""
    mode = 0o444 if readonly else 0o644
    os.chmod(path, mode)
    return oct(mode)


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def convert(
    md_path: Path, pdf_path: Path, *,
    title: str | None = None, subtitle: str = "", tag: str = "文档",
    brand: str = BRAND_NAME, ip_notice: str = IP_NOTICE_DEFAULT,
    logo: Path | None = None, mode: str = "report",
    readonly: bool = True, allow_copy: bool = False,
    owner_password: str = DEFAULT_OWNER_PW,
    paper: str = "A4", landscape: bool = False,
    keep_html: bool = False,
) -> dict:
    md_text = md_path.read_text(encoding="utf-8")
    logo_path = logo if logo else DEFAULT_LOGO
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    doc = md2html.build_document(
        md_text, title=title, subtitle=subtitle, brand=brand,
        ip_notice=ip_notice, logo_path=logo_path, mode=mode,
        source_name=md_path.name, generated_at=generated_at, tag=tag,
    )

    # 输出文件若已被置为只读，先解锁以便覆盖
    if pdf_path.exists() and not os.access(pdf_path, os.W_OK):
        os.chmod(pdf_path, 0o644)

    work = Path(tempfile.mkdtemp(prefix="xyb-md2pdf-"))
    try:
        html_path = work / (md_path.stem + ".html")
        html_path.write_text(doc["html"], encoding="utf-8")

        logo_uri = ""
        if logo_path and logo_path.exists():
            logo_uri = md2html.logo_data_uri(logo_path)

        sub = doc.get("subtitle") or ""
        right = sub if sub else datetime.now().strftime("%Y-%m-%d")
        render_pdf(
            html_path, pdf_path,
            header=header_template(brand, doc["title"], logo_uri, right),
            footer=footer_template(brand),
            paper=paper, landscape=landscape,
        )

        result: dict = {
            "source": str(md_path),
            "pdf": str(pdf_path),
            "title": doc["title"],
            "pages": 0,
            "size_kb": 0.0,
            "readonly": readonly,
            "allow_copy": allow_copy,
        }
        if readonly:
            subject = f"{brand}整理 · {ip_notice[:120]}"
            result["permissions"] = apply_readonly(
                pdf_path, title=doc["title"], subject=subject,
                allow_copy=allow_copy, owner_password=owner_password,
            )
        result["file_mode"] = set_file_readonly(pdf_path, readonly)

        try:
            from pypdf import PdfReader
            result["pages"] = len(PdfReader(str(pdf_path)).pages)
        except Exception:  # noqa: BLE001
            pass
        result["size_kb"] = round(pdf_path.stat().st_size / 1024, 1)

        if keep_html:
            html_out = pdf_path.with_suffix(".html")
            shutil.copy2(html_path, html_out)
            result["html"] = str(html_out)
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Markdown → 小胰宝社区品牌 PDF（原文 + logo + IP 归属 + 默认只读）"
    )
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 PDF 路径（默认同名同目录）")
    ap.add_argument("--title", help="覆盖标题（默认取第一个一级标题）")
    ap.add_argument("--subtitle", default="", help="副标题，如日期行")
    ap.add_argument("--tag", default="文档", help="封面右上角标签，如 监测日报")
    ap.add_argument("--brand", default=BRAND_NAME)
    ap.add_argument("--ip-notice", default=IP_NOTICE_DEFAULT)
    ap.add_argument("--logo", help="自定义 logo 图片路径")
    ap.add_argument("--mode", choices=["report", "plain"], default="report")
    ap.add_argument("--paper", default="A4", choices=["A4", "Letter", "A3"])
    ap.add_argument("--landscape", action="store_true")
    ap.add_argument("--html", action="store_true", help="同时保留品牌化 HTML")
    ap.add_argument("--no-readonly", action="store_true", help="不施加只读限制")
    ap.add_argument("--allow-readonly-copy", dest="allow_copy", action="store_true",
                    help="只读模式下仍允许复制文字")
    ap.add_argument("--owner-password", default=DEFAULT_OWNER_PW)
    ap.add_argument("--open", action="store_true", help="生成后打开 PDF")
    args = ap.parse_args()

    md_path = Path(args.input).expanduser().resolve()
    if not md_path.exists():
        print(f"错误：找不到输入文件 {md_path}", file=sys.stderr)
        return 2
    pdf_path = Path(args.output).expanduser().resolve() if args.output else md_path.with_suffix(".pdf")

    result = convert(
        md_path, pdf_path,
        title=args.title, subtitle=args.subtitle, tag=args.tag,
        brand=args.brand, ip_notice=args.ip_notice,
        logo=Path(args.logo).expanduser() if args.logo else None,
        mode=args.mode, readonly=not args.no_readonly,
        allow_copy=args.allow_copy, owner_password=args.owner_password,
        paper=args.paper, landscape=args.landscape, keep_html=args.html,
    )

    print(f"✅ PDF 已生成：{result['pdf']}")
    print(f"   标题：{result['title']} ｜ 页数：{result['pages']} ｜ "
          f"大小：{result['size_kb']} KB ｜ 文件权限：{result['file_mode']}")
    if result.get("permissions"):
        p = result["permissions"]
        print(f"   只读：加密={p['encrypted']} 可打印={p['can_print']} "
              f"可修改={p['can_modify']} 可复制={p['can_copy']}")
    print("RESULT " + json.dumps(result, ensure_ascii=False))

    if args.open:
        os.system(f'open "{result["pdf"]}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
