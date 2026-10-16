# 定时任务用的取用提示词（xyb-md2pdf）

把下面整段粘进定时任务的提示词即可。定时任务看不到历史对话，所以这里把路径与要求都写全了。

---

## A. 标准版：日报生成后顺手转 PDF

```text
把本次产出的监测日报 Markdown 转成小胰宝社区品牌 PDF，并交付给用户。

使用 xyb-md2pdf 技能（目录：/Users/qinxiaoqiang/.workbuddy/skills/xyb-md2pdf）：

1. 输入：本次自动化生成的最新一份日报 .md（在报告的 reports 目录里取当天日期的那一份）。
2. 执行：
   PY=/Users/qinxiaoqiang/.workbuddy/binaries/python/envs/default/bin/python
   $PY /Users/qinxiaoqiang/.workbuddy/skills/xyb-md2pdf/scripts/md2pdf.py "<日报.md 的绝对路径>" \
       --tag "监测日报" --subtitle "报告日期：<YYYY-MM-DD>"
3. 硬要求：
   - 原文一字不改：不改写、不增删、不"顺手修错别字"，只做版式转换；
   - 页眉带小胰宝社区 logo，「小胰宝社区维护」与版权归属声明出现在每页页脚和文末；
   - 输出 PDF 默认只读：允许打印，禁止修改、注释、复制文字；
   - 输出路径与 md 同目录同名（除非我另行指定）。
4. 完成后用 present_files 打开 PDF，并在回复首行写清：PDF 绝对路径、页数、只读状态。
```

---

## B. 精简版：只要 PDF，不要附件

```text
把 <md 文件绝对路径> 转成小胰宝社区品牌 PDF：调用 xyb-md2pdf 技能
（/Users/qinxiaoqiang/.workbuddy/skills/xyb-md2pdf/scripts/md2pdf.py），
原文不改写，页眉带 logo，页脚与文末带「小胰宝社区维护」和版权归属，输出默认只读。
完成后 present_files 打开，并报告路径、页数、只读状态。
```

---

## C. 变体开关

| 需求 | 追加参数 |
|---|---|
| 允许别人复制文字 | `--allow-readonly-copy` |
| 明确不要只读 | `--no-readonly` |
| 换奔跑造型 logo | `--logo /Users/qinxiaoqiang/.workbuddy/skills/xyb-md2pdf/assets/xyb-logo-running.jpg` |
| 极简版式（不要封面大图） | `--mode plain` |
| 同时留一份 HTML | `--html` |
| 封面标签换成别的 | `--tag "临床情报"` |

---

## D. 自动化里怎么读结果

脚本最后一行固定输出 `RESULT {json}`，字段：`pdf` / `pages` / `size_kb` / `file_mode` /
`permissions.can_print` / `permissions.can_modify` / `permissions.can_copy`。
只读是否生效，看 `can_modify` 与 `can_copy` 是否为 `false`。
