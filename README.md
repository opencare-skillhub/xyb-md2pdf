# xyb-md2pdf

将 Markdown 文档转换为小胰宝社区品牌 PDF 或独立 HTML。正文内容按原文保留，并自动添加社区标识、版权归属说明、文档元数据和可选的 PDF 只读权限。适用于监测日报、临床情报、白皮书、会议纪要和其他社区文档。

## 功能

- 自动读取 Markdown 标题和头部元信息，生成品牌封面、页眉、页脚及文末版权声明。
- 保留标题、段落、列表、引用、代码块、表格、链接和状态标签等结构。
- PDF 默认 A4 纵向，页边距为上 16mm、下 18mm、左右 18mm；标题和段落设置分页保护，表格跨页时重复表头。
- HTML 使用居中阅读区和响应式布局；窄屏保留表格可读宽度并横向滚动。
- PDF 默认施加只读权限：允许打印，禁止编辑、注释和复制；文件权限设为 `0444`。
- 支持导出独立 HTML，Logo 以内嵌数据方式写入，不依赖旁置图片。

## 快速开始

克隆仓库后，安装 Python 依赖并准备可供 Playwright 使用的 Chrome/Chromium：

```bash
git clone git@github.com:opencare-skillhub/xyb-md2pdf.git
cd xyb-md2pdf
python3 -m pip install markdown playwright pypdf cryptography
python3 -m playwright install chromium
```

生成同名 PDF：

```bash
python3 scripts/md2pdf.py report.md
```

生成日报 PDF，并同时保留 HTML：

```bash
python3 scripts/md2pdf.py report.md \
  --tag "监测日报" \
  --subtitle "报告日期：2026-10-16" \
  --html
```

只生成品牌化 HTML：

```bash
python3 scripts/md2html.py report.md -o report.html
```

默认输出在源文件旁边。指定 `-o output.pdf` 可改变 PDF 输出位置；启用 `--html` 时 HTML 使用相同路径和 `.html` 扩展名。

## 排版与分页

屏幕 HTML 最大宽度为 1020px，桌面端左右留白 48px，窄屏留白 18px。PDF 正文行高约 1.8，段落后距 3mm，列表项后距 2.5mm。表格首列最小宽度为 14mm，避免短标签被逐字挤压；过宽表格可在手机上横向滚动。

打印时标题尽量与后文保持相邻，段落避免在页底留下孤行，表格行尽量不拆分。需要手动从新页开始时，可在 Markdown 中独占一行插入：

```html
<div class="page-break"></div>
```

分段请在 Markdown 源文中使用空行。转换器保留已有段落，不改写正文。

## 常用参数

| 参数 | 说明 |
| --- | --- |
| `-o`, `--output` | 指定 PDF 输出路径 |
| `--title` | 覆盖自动读取的文档标题 |
| `--subtitle` | 设置封面副标题，也用于页眉 |
| `--tag` | 设置封面标签，例如「监测日报」 |
| `--brand` | 设置品牌名称 |
| `--logo` | 指定替代 Logo 图片 |
| `--mode report\|plain` | 选择完整封面或简洁版式 |
| `--paper A4\|Letter\|A3` | 选择纸张大小 |
| `--landscape` | 使用横向页面 |
| `--html` | 同时输出品牌化 HTML |
| `--no-readonly` | 关闭 PDF 只读权限 |
| `--allow-readonly-copy` | 只读 PDF 允许复制文字 |

完整触发条件和行为说明见 [SKILL.md](SKILL.md)，样式令牌见 [design-tokens.md](references/design-tokens.md)，只读与版权说明见 [readonly-and-ip.md](references/readonly-and-ip.md)。

## 文件结构

```text
xyb-md2pdf/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── check-version.sh
├── scripts/
│   ├── md2html.py
│   └── md2pdf.py
├── references/
├── templates/
└── assets/
```

## 依赖与说明

- Python 3
- `markdown`（缺少时 Markdown 转换会使用内置简化解析器）
- `playwright` 与 Chrome/Chromium（HTML 打印为 PDF）
- `pypdf`（PDF 元数据和权限）
- `cryptography`（优先启用 AES-256；不可用时回退到兼容加密算法）

只读标志限制常见 PDF 阅读器中的编辑、注释和复制操作，不等同于对内容加密保密；PDF 打开不需要用户密码。源 Markdown 不会被修改。正文可能包含第三方内容时，文末版权说明会保留原作者或原机构的权利归属。

## 维护

修改样式后同步更新 `references/design-tokens.md`；实质性改动须更新 `SKILL.md` 版本号和 `CHANGELOG.md`。提交前运行：

```bash
./check-version.sh
```

## License

代码采用 MIT License，见 [LICENSE](LICENSE)。生成文档中的社区名称、Logo、IP 归属声明及第三方材料权利不由代码许可证改变。
