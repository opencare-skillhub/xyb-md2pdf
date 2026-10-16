# 只读实现与 IP 归属规范（xyb-md2pdf）

## 一、「只读」包含两层，缺一层都不算

### 第 1 层：文档权限（PDF 内部）

用 `pypdf` 对成品做 AES-256 加密，写入权限位：

| 项 | 值 | 含义 |
|---|---|---|
| `/P` | `2052` | `PRINT(4) + PRINT_TO_REPRESENTATION(2048)` |
| 用户密码 | 空 | 打开时**不弹密码框**，任何人都能阅读 |
| 所有者密码 | `xyb-community`（默认，可 `--owner-password` 改） | 用于解除限制 |
| 允许 | 阅读、打印（含高保真打印） | |
| 禁止 | 修改 `MODIFY`、注释 `ADD_OR_MODIFY`、填写表单 `FILL_FORM_FIELDS`、拼装页面 `ASSEMBLE_DOC` | |
| 禁止（默认） | 复制/提取文字 `EXTRACT_TEXT_AND_GRAPHICS` | 加 `--allow-readonly-copy` 可放开 |

### 第 2 层：文件系统权限

输出文件 `chmod 0444`（`-r--r--r--`）。再次生成同一路径时脚本会先 `chmod 0644` 解锁再写回，**不需要手动处理**。

## 二、自查命令

```bash
PY=/Users/qinxiaoqiang/.workbuddy/binaries/python/envs/default/bin/python

# 看权限位与加密算法（raw_p 应为 2052）
$PY - <<'EOF'
from pypdf import PdfReader
r = PdfReader("out.pdf")
print("encrypted:", r.is_encrypted)
print("meta:", r.metadata)
enc = r.trailer.get("/Encrypt")
print("/P:", enc.get("/P"), "| CFM:", enc.get("/CF", {}).get("/StdCF", {}).get("/CFM"))
print("user_access_permissions:", r.user_access_permissions)
EOF

# 看文件模式（应为 444）
stat -f "%Sp %N" out.pdf
```

脚本自身每次都会打印 `RESULT {json}`，其中 `permissions.can_modify` 与 `permissions.can_copy` 应为 `false`。

## 三、实现上的两个坑（都已修）

1. **IntFlag 判断写错会误报**
   `UserAccessPermissions` 是 IntFlag。`perms.MODIFY` 取的是枚举成员本身，恒为真值，于是「可修改」永远显示 True。必须写成 `bool(perms & P.MODIFY)`。
   pypdf 的 `encrypt()` 在缺 `cryptography` 时抛 `DependencyError`，而错误发生在 `write()` 阶段（延迟执行），只 try 住 `encrypt()` 是接不住的。现改为：先探测 `cryptography` 是否可用，再整体 try/except 降级 RC4-128。

2. **加密与元数据写入顺序**
   先 `add_metadata()` 再 `encrypt()`，否则元数据可能落在未加密的明文区或被丢弃。写文件时先落临时文件 `*.ro.pdf` 再 `os.replace()` 原子替换。

## 四、各阅读器对权限的实际态度

| 阅读器 | 行为 |
|---|---|
| Adobe Acrobat / Reader | **遵守**权限位：工具栏的编辑、注释灰掉；复制被拦截 |
| macOS 预览（Preview） | 尊重「不可修改」，但复制开关常被忽略——真正的复制限制以 Acrobat 为准 |
| Chrome / Edge 内置阅读器 | 基本**忽略**权限位，仍可下载与打印 |
| 微信 / 企业微信内置预览 | 只读浏览，无编辑入口 |

结论：文档权限层是「防误改、表明态度」，不是防破解的强保护；需要更强保护时应改用加水印或分发图片版。**文件系统 0444 才是本地防覆盖的真正抓手。**

## 五、IP 归属（版权声明）规范

**三处必现**，缺一处即视为不规范：

1. **每页页脚**：`小胰宝社区维护 ｜ © 年份 小胰宝社区 · 版权归小胰宝社区所有 ｜ 不构成医疗或投资建议`
2. **文末尾注块**：完整声明（默认文案见下），并附「原始文档：xxx.md ｜ 生成时间：yyyy-mm-dd hh:mm」
3. **PDF 元数据**：`/Author = 小胰宝社区`、`/Creator = 小胰宝社区 xyb-md2pdf`、`/Subject` 前缀「小胰宝社区整理 · 」，`/Keywords` 含「版权归小胰宝社区所有」

默认声明文案（`scripts/md2html.py` 的 `IP_NOTICE_DEFAULT`，可用 `--ip-notice` 覆盖）：

> 本文件由小胰宝社区维护整理并发布。除标注来源的第三方内容外，本文件的整理、编排与呈现版权归小胰宝社区（XiaoYiBao Community）所有。本文件仅用于社区内部学习与信息共享，不构成医疗建议、诊疗依据或投资建议，不得用于商业用途；第三方内容的版权归原作者及原机构所有。

口径红线（与社区内容规范一致）：

- **不做医院/患者推荐排名、不替代临床判断、资助不购买结论**。
- 报告内的「未核实/待核实」状态不得在转 PDF 过程中被改成确定结论——样式可以变，措辞不能动。
- 声明里必须保留「不构成医疗建议」；若文档用于对外分发，另需保留第三方版权归属句。
