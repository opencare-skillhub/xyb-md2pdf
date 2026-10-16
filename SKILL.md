---
name: xyb-md2pdf
description: 把 Markdown 文档规范转换为小胰宝社区品牌 PDF——完整保留原文，自动加小胰宝社区 logo 与版权（IP）归属声明，输出默认为只读。当用户要求「把 md 转成 pdf」「转 PDF」「导出 PDF」「日报转 PDF」「加上社区 logo 和署名后出 PDF」，或直接提到 xyb-md2pdf、小胰宝 PDF、社区品牌 PDF 时使用。输入是 Markdown（含表格、链接、多级列表的监测日报、临床情报、白皮书、会议纪要、社区文档等），输出为同名 .pdf；也可只产出品牌化 HTML。触发词：转pdf、md转pdf、导出pdf、日报pdf、报告转pdf、加logo、版权归属、IP归属、只读pdf、小胰宝社区维护。
agent_created: true
---

# 小胰宝 Markdown → PDF（xyb-md2pdf）v1.1.0

把 Markdown 原文「规范地」变成一份可以直接发给社区病友与家属的 PDF：版式统一、带小胰宝社区 logo、带版权归属声明、默认只读。

## 一、三条不可动摇的规则

1. **原文零改写**——只做结构转换与样式注入，不改写、不删减、不补写正文任何文字；数字、药物名、试验编号、结论一律照抄。即使发现 md 里有错别字或疑似笔误，也只提示、不动手。
2. **只读是默认**——输出 PDF 默认施加只读（禁修改、禁注释、禁填表，默认连复制文字一并禁止），并把文件系统权限置为 `0444`。确实需要可编辑时，显式加 `--no-readonly`。
3. **IP 归属不可省**——页脚与文末必须出现「小胰宝社区维护 + 版权归属声明」；正文含第三方来源时，声明须写明第三方内容版权归原作者/原机构，且不得用于商业用途。

## 二、执行方式

```bash
PY=/Users/qinxiaoqiang/.workbuddy/binaries/python/envs/default/bin/python
$PY <SKILL_DIR>/scripts/md2pdf.py <输入.md> [选项]
```

`<SKILL_DIR>` = `~/.workbuddy/skills/xyb-md2pdf`。

| 选项 | 作用 |
|---|---|
| `-o out.pdf` | 输出路径（默认与 md 同名同目录） |
| `--tag 监测日报` | 封面右上角标签，默认「文档」 |
| `--subtitle "报告日期：2026-10-16"` | 副标题（也用作页眉右侧文字） |
| `--title "..."` | 覆盖标题（默认取 md 第一个一级标题） |
| `--brand 小胰宝社区` | 品牌名（署名与页眉页脚都用它） |
| `--logo <图片>` | 换 logo；默认 `assets/xyb-mascot.png`（透明底），`assets/xyb-logo-running.jpg` 为奔跑造型 |
| `--mode report\|plain` | `report` 默认（品牌封面 + 完整版式）；`plain` 极简（无封面大图） |
| `--ip-notice "..."` | 覆盖版权归属声明文案 |
| `--html` | 同时保留品牌化 HTML |
| `--no-readonly` | 不做只读限制 |
| `--allow-readonly-copy` | 保持只读，但允许复制文字 |
| `--paper A4\|Letter\|A3`、`--landscape`、`--open` | 纸张、横版、生成后打开 |

只想要品牌化 HTML：`$PY <SKILL_DIR>/scripts/md2html.py in.md -o out.html`

脚本结束会打印一行 `RESULT {json}`（含 `pages` / `size_kb` / `permissions` / `file_mode`），自动化里可直接解析取用。

## 三、执行后的收尾动作（每次都要做）

1. **必须**用 `present_files` 打开生成的 PDF。
2. 在回复里报告三件事：输出路径、页数、只读状态（可打印 / 不可改 / 不可复制）。
3. md 若有明显缺陷（缺标题、表格列数不齐、疑似含敏感信息），只提示，不擅自修改原文。

## 四、版式与分页默认值

- HTML 屏幕阅读区最大宽度 1020px，桌面端左右留白 48px，窄屏左右留白 18px；窄屏表格保留可读列宽并横向滚动，不挤压单元格内容。
- PDF 默认 A4 左右边距 18mm，上 16mm、下 18mm（给重复页眉页脚留空间）。正文行高约 1.8，段落间距 3mm，列表项间距 2.5mm；h2/h3/h4 有足够前后留白。
- 打印时标题与后续内容保持相邻；段落控制孤行/寡行并尽量保持整段，表格重复表头且避免拆开单行。短列表、引用、代码块与文末署名尽量整体分页。
- 需要从新页开始时，可在 Markdown 中单独插入原始 HTML：`<div class="page-break"></div>`。这只影响版式，不改正文内容。
- 长段落如需表达多个独立意思，请在源 Markdown 中用空行分段；转换器保留段落结构，不改写正文。
- `--html` 生成的是带 viewport、屏幕留白和可打印分页规则的独立 HTML；Logo 使用内嵌数据，不依赖旁置图片。

## 五、输出规范（脚本已自动完成）

- **封面**：logo + 「小胰宝社区 · 维护出品」+ 标题 + 副标题 + 自动抽取的元信息标签（md 头部 `**键**：值` 行会变成标签）
- **正文**：h2 薄荷绿左竖条；表格品牌绿表头 + 隔行浅底 + 表格首列至少 14mm 宽，避免中文标签逐字换行；状态标签自动生成（两条规则：`**已核实**` 这类独立加粗词，以及「整格只有状态词」的表格单元格，如 `| 待核实（付费墙） |`，关键词成标签、括注保留为普通文字）；裸 URL 自动成链；`>` 引用转为浅底提示块
- **页眉**（每页重复）：logo + 小胰宝社区 + 文档名 + 副标题/日期
- **页脚**（每页重复）：小胰宝社区维护 ｜ © 年份 小胰宝社区 · 版权归小胰宝社区所有 ｜ 不构成医疗或投资建议 ｜ 第 X / Y 页
- **文末**：完整 IP 归属声明 + 原始文档名 + 生成时间
- **PDF 元数据**：`/Title`、`/Author`（小胰宝社区）、`/Subject`（含归属声明）、`/Creator`、`/Keywords` 一并写入

## 六、只读是怎么落地的

两层叠加，缺一层都不算「只读」：

1. **文档权限层**（pypdf，AES-256 加密）：`/P = 2052`，即只允许阅读与打印，禁止修改、注释、填表、拼装；默认也禁止复制文字（`--allow-readonly-copy` 可放开复制）。用户密码为空，所以打开时**不会**弹密码框。
2. **文件系统层**：输出文件 `chmod 0444`。

再次生成同一个文件时脚本会**先自动解锁再写回**，不需要手动 `chmod`。

细节、自查命令与已知限制见 `references/readonly-and-ip.md`。

## 七、已知坑（实战踩过）

- **AES-256 依赖 `cryptography`**：环境缺库时脚本自动降级 RC4-128，只读权限照常生效（算法字段会显示 `RC4-128`）。
- **复核权限位必须用位与**：`perms.MODIFY` 这种写法在 IntFlag 下恒为真，会误报「可修改」。要写 `perms & P.MODIFY`。
- **Chrome 页眉页脚模板是独立渲染上下文**：不吃页面 CSS，只能用内联样式；logo 要以 data URI 内嵌。
- **`markdown` 库缺失会回落内置转换器**：功能略简（不支持脚注、属性列表等），日常 md 无感。
- **页眉右侧文字取自 `--subtitle`**：不传则显示当天日期。

## 八、相关文件

- `scripts/md2pdf.py` — 主入口：md → HTML → PDF → 只读 + 元数据
- `scripts/md2html.py` — markdown → 品牌化 HTML（含品牌令牌与全部样式）
- `references/design-tokens.md` — 色板、字体、版式、组件样式（改样式先看这里）
- `references/readonly-and-ip.md` — 只读实现、自查命令、IP 归属文案口径
- `templates/prompt-定时任务.md` — 可粘贴进定时任务的取用提示词
- `assets/xyb-mascot.png`、`assets/xyb-logo-running.jpg` — 默认与备用 logo
