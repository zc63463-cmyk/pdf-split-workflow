---
title: Trae PDF 分片工作流指南
version: "4.0"
date: 2026-04-18
tags:
  - pdf
  - split
  - workflow
  - guide
aliases:
  - PDF分片指南
  - 分片工作流
---

# Trae PDF 分片工作流指南（v4.0）

> 本指南记录了 PDF 按章节/小节分片的完整工作流、核心要点和常见陷阱，供其他 Trae 对话复用。
> 基于 **14 本**教材/参考书的实际分片经验迭代优化。

> [!tip] v4.0 主要更新
> - 新增 **§十三 Trae 部署细节**（Agent 操作手册）：工具编排策略、上下文管理、错误恢复、调试技巧、Plan Mode 工作流、性能优化、环境约束
> - 新增 **文本层 PDF 的节标题自动提取**方案（正则匹配 `X.Y 标题`）
> - 新增 **书签 null 字节陷阱**及修复方案
> - 新增 **无用书签检测**策略（书签存在但无实际标题）
> - 新增 **两篇/多部分书籍**的分片策略（习题+实验指导）
> - 新增 **三级标题合并**策略（子实验不单独分片）
> - 新增 **重复文件夹清理**经验（书签解析产生的冗余目录）
> - 完善 **末节结束页 bug**的通用防护方案
> - 新增 **模板 C：书签驱动分片**脚本
> - 更新 **已处理书籍清单**（14 本）
> - 优化分片脚本模板（增加安全检查和边界防护）

---

## 一、任务概述

将一本 PDF 教材按章节（或小节）拆分为独立 PDF 文件，便于按知识点检索和阅读。

---

## 二、分片前探索（必做）

### 2.1 读取 PDF 基本信息

```python
from pypdf import PdfReader
reader = PdfReader(pdf_path)
print(f"总页数: {len(reader.pages)}")
print(f"元数据: {reader.metadata}")
```

### 2.2 检查书签（优先方案）

```python
outline = reader.outline
def print_outline(items, level=0):
    for item in items:
        if isinstance(item, list):
            print_outline(item, level + 1)
        else:
            page = reader.get_destination_page_number(item)
            print(f"{'  '*level}{item.title} -> 第{page+1}页")
```

**有书签 → 直接用书签页码分片，最可靠。** 但需注意：
- 跳过与子书签同页的父书签（会产生 0 页空文件）
- 扁平书签层级过深时，只取章级别书签

### 2.3 判断 PDF 类型

```python
text = reader.pages[0].extract_text()
```

| extract_text() 结果 | 判断 | 处理方式 |
|---|---|---|
| 返回空字符串或长度 < 50 | **扫描版** | 用 Read 工具或 OCR |
| 有文本但全是乱码 | **扫描版**（文本层编码异常） | 用 Read 工具或 OCR |
| 有正常中文/英文文本 | **文本版** | 可直接提取文本辅助定位 |

> [!warning] 常见情况
> iOS Quartz PDFContext 生成的 PDF，`extract_text()` 返回空字符串，但并非真正的"扫描版"——而是生成时未嵌入文本层。处理方式与扫描版相同。

### 2.4 无书签时的页码获取方案

**按优先级排序：**

| 方案 | 可靠性 | 适用场景 | 耗时 |
|------|--------|---------|------|
| **Read 工具逐页扫描** | ⭐⭐⭐⭐⭐ | 所有 PDF | 高（但最准确） |
| **文本层正则提取**（v4.0 新增） | ⭐⭐⭐⭐⭐ | 有文本层的 PDF | 低（自动化） |
| OCR 目录页 + Read 校验 | ⭐⭐⭐⭐ | 有清晰目录页的 PDF | 中 |
| 纯 OCR 全书扫描 | ⭐⭐ | 无目录页 | 极高 |
| 按比例估算 | ⭐ | 同系列教材 | 低（但误差大） |

**关键经验：tesseract OCR 对中文数学教材效果很差**，尤其是：
- 数学公式完全无法识别
- § 符号经常丢失
- 页码数字识别错误率高

**推荐流程：**
1. **有文本层**：用正则匹配 `X.Y 标题` 格式自动提取节标题（见 §2.4.1）
2. **无文本层**：先用 pdf2image 转目录页为图片（dpi=200），再用 Read 工具查看
3. 如果目录页信息不足，转正文页面用 Read 工具逐页扫描小节标题

#### 2.4.1 文本层节标题自动提取（v4.0 新增）

> [!tip] 适用于有文本层的 PDF（如算法导论、逻辑学导论）
> 通过正则匹配页面文本中的 `X.Y 标题` 格式，自动定位所有小节起始页。

```python
import re
from pypdf import PdfReader

reader = PdfReader(pdf_path)
section_pattern = re.compile(r'^(\d+\.\d+)\s+(.{2,40})$')

for p in range(ch_start - 1, ch_end):
    text = reader.pages[p].extract_text() or ""
    for line in text.split('\n'):
        line = line.strip()
        m = section_pattern.match(line)
        if m:
            sec_num = m.group(1)
            sec_chapter = int(sec_num.split('.')[0])
            if sec_chapter != current_chapter:
                continue  # 跳过不属于当前章的节
            sec_title = m.group(2)
            print(f"  {sec_num} {sec_title} -> PDF p{p+1}")
            break  # 每页只取第一个匹配
```

**注意事项：**
- 必须过滤误匹配：章节小结（如 `1.1 节 说明什么是逻辑学...`）不是真正的节标题
- 过滤规则：标题长度通常 < 40 字符，且不包含 `节` 字开头
- 某些 PDF 的节标题可能跨行（标题太长换行），需要拼接处理
- 每页只取第一个匹配，避免匹配到正文中的编号引用

### 2.5 检测是否为合并 PDF

> [!important] 关键判断
> 有些 PDF 是由多个独立 PDF 合并而成，每个子文件的页码从 1 重新开始。这类 PDF **不存在全局 OFFSET**，需要特殊处理。

**识别方法：**

在分片前探索阶段，查看多个章节起始页的底部页码：
- 如果第1章起始页底部显示页码 1，第2章起始页底部也显示页码 1 → **合并 PDF**
- 如果第1章起始页底部显示页码 1，第2章起始页底部显示页码 47 → **连续编页 PDF**

```python
# 快速检测：查看几个疑似章节起始页的底部页码
from pdf2image import convert_from_path
for p in [6, 52, 112]:
    images = convert_from_path(pdf_path, first_page=p, last_page=p, dpi=150)
    images[0].save(f"check_p{p}.png")
    # 用 Read 工具查看底部页码
```

**合并 PDF 的影响：**
- ❌ 不存在全局 OFFSET（每个章节内部页码独立）
- ❌ 章节之间不需要重叠页策略
- ✅ 直接使用 PDF 绝对页码进行章节级分片
- ✅ 小节级分片时，每个章节内部 OFFSET = 0

### 2.6 无用书签检测（v4.0 新增）

> [!warning] 书签存在 ≠ 书签有用
> 有些 PDF 有大量书签，但内容完全无用。

**典型案例：**
- 《数据库系统概论 第6版》：478 个书签，但全部是数字 `1`-`75`，无任何章节标题
- 产生原因：可能是 PDF 制作工具自动生成的页码书签

**检测方法：**
```python
outline = reader.outline
# 检查书签标题是否都是纯数字
all_numeric = all(
    (item.title or "").replace('\x00', '').strip().isdigit()
    for item in outline if not isinstance(item, list)
)
if all_numeric:
    print("⚠ 书签全部为纯数字，无用！需基于 TOC 手动构建分片数据")
```

**处理方式：**
- 无用书签 → 当作无书签处理，使用 Read 工具扫描目录页或文本层正则提取

---

## 三、确定页码偏移量（关键步骤）

**大多数教材的书籍页码 ≠ PDF 页码**，因为前面有封面、序言、目录等前置内容。

### 确定方法

1. 找到正文第一章的起始 PDF 页码
2. 找到该页上显示的书籍页码（通常为 1）
3. `OFFSET = PDF页码 - 书籍页码`

### 验证方法

```python
from pdf2image import convert_from_path
images = convert_from_path(pdf_path, first_page=23, last_page=23, dpi=150)
images[0].save("check.png")
# 用 Read 工具查看 check.png，确认页码
```

**⚠ 常见错误：偏移量差 1-2 页。** 必须通过查看实际页面底部的页码数字来确认，不能靠猜。

**双重验证技巧（v4.0 新增）：**
```python
# 同时验证起始和末尾
# 起始：PDF p29 = 书 p3 → OFFSET = 26
# 末尾：PDF p498 = 书 p472 → OFFSET = 26 ✓
# 两端验证可排除 ±1 偏差
```

### 合并 PDF 特殊情况

> [!note] 合并 PDF 无需全局 OFFSET
> 如果检测到 PDF 是合并类型（见 §2.5），则：
> - **章节级分片**：直接使用 PDF 绝对页码，无需 OFFSET
> - **小节级分片**：每个章节内部页码从 1 开始，OFFSET = 0
> - 跳过本节剩余内容，直接进入页码获取阶段

---

## 四、分片粒度选择

| 策略 | 适用场景 | 输出结构 |
|------|---------|---------|
| **按章分片** | 章节少（<10章）、每章篇幅适中 | `章节内容/第X章_标题.pdf` |
| **按小节分片** | 每章小节多且独立、需精细检索 | `章节内容/第X章_标题/小节编号_标题.pdf` |
| **按书签分片** | PDF 有完整书签结构 | 直接用书签名称和页码 |

> [!tip] 推荐策略
> 先按章分片（快速），验证无误后再按小节分片（精细）。两阶段递进可以提前发现页码错误，降低返工成本。

### 三级标题分片决策（v4.0 新增）

> [!note] 何时需要拆分三级标题？
> 某些书籍有三层结构：章 → 节 → 子节/子实验。

| 情况 | 建议 | 理由 |
|------|------|------|
| 子节仅 2-4 页 | **不单独分片**，合并到父节 | 分片过碎，管理成本高 |
| 子节逻辑关联紧密 | **不单独分片**，合并到父节 | 如实验 3.1-3.6 都是 SQL 实验 |
| 子节篇幅独立且较长（>10 页） | 可单独分片 | 按需决定 |

**实战案例：** 《数据库习题解析》的实验指导部分，实验 3.1-3.6（SQL 查询与操纵的 6 个子实验）合并为一个 PDF 文件。

---

## 五、页码获取：方案详解

### 方案 A：文本层正则提取（v4.0 新增，推荐用于文本版 PDF）

适用于：`extract_text()` 能返回正常文本的 PDF。

```python
import re
section_pattern = re.compile(r'^(\d+\.\d+)\s+(.{2,40})$')
false_positive_patterns = [r'节\s']  # 过滤 "X.Y 节 ..." 等小结行

for p in range(ch_start - 1, ch_end):
    text = reader.pages[p].extract_text() or ""
    for line in text.split('\n'):
        m = section_pattern.match(line.strip())
        if m and not any(re.search(p, m.group(2)) for p in false_positive_patterns):
            print(f"  {m.group(1)} {m.group(2)} -> p{p+1}")
            break
```

### 方案 B：Read 工具逐页扫描（推荐，最准确）

适用于：无书签、OCR 效果差的 PDF。

#### 两阶段采样法

> [!tip] 相比 v2 的"二分法"，两阶段采样法更直观、更不容易遗漏

**阶段一：粗扫（确定大致范围）**

```python
from pdf2image import convert_from_path
import os

os.makedirs("/data/user/work/pages", exist_ok=True)
step = 6
for p in range(1, total_pages + 1, step):
    images = convert_from_path(pdf_path, first_page=p, last_page=p, dpi=100)
    images[0].save(f"/data/user/work/pages/p{p:03d}.png")
```

用 Read 工具查看每个采样点，记录该页属于哪个 § 节。

**阶段二：精扫（精确定位标题页）**

在粗扫发现的相邻 § 节之间，逐页扫描找到标题的精确起始页。

#### 并行扫描技巧

> [!tip] 使用 Task 工具并行扫描多个章节
> - 每个子代理负责 2-4 个章节的采样图片分析
> - 最多同时启动 3 个子代理（系统限制）

### 方案 C：OCR 目录页 + Read 校验

适用于：有清晰目录页的 PDF。

### 方案 D：按比例估算（仅限同系列教材）

**⚠ 教训：比例估算误差很大，曾导致多个 0 页和负数页文件。** 仅在没有其他方案时使用。

---

## 六、重叠页策略（核心要点）

### 为什么需要重叠？

教材中常见排版：**上一小节的习题和下一小节的标题在同一页**。

如果严格按页码切割（`end = 下一节起始页 - 1`），会导致：
- 上一节丢失末尾习题
- 下一节丢失章节标题

### 重叠页决策树

```
需要分片的两个相邻部分是否需要重叠页？
│
├─ 它们属于同一本书的连续编页内容？
│   ├─ 是 → 需要重叠页（上一节末尾和下一节标题可能同页）
│   └─ 否 → 它们是合并 PDF 的不同子文件？
│       ├─ 是 → 不需要重叠页（子文件之间无跨页内容）
│       └─ 否 → 需要重叠页（保守策略）
```

### 同页多节处理（v4.0 新增）

> [!note] 多个小节可能从同一页开始
> 当目录中多个小节标注相同起始页码时（如 1.1 和 1.2 都从书 p3 开始），说明它们在同一页上。overlap 策略下这是正确的——两个文件都从该页开始。

**实战案例：** 《数据库习题解析》第1章，1.1（基本知识点）和 1.2（习题解答和解析）都从书 p3 开始，因为章节标题页上同时列出了该章所有小节标题。

### 解决方案

```python
# 每个小节的结束页 = 下一小节的起始页（而非起始页 - 1）
if i + 1 < len(sections):
    book_end = sections[i + 1][2]  # 下一节起始页
```

---

## 七、页码校验（必做）

**OCR 识别的目录页码可能有误差，目录页码也可能与实际标题页不一致。**

### 校验流程

1. 列出所有小节起始页码
2. 对每个起始页，转换为图片并用 **Read 工具**查看
3. 确认该页是否确实包含对应的小节标题
4. 如果标题在前一页就出现了，则修正起始页码

### 节标题格式多样性

> [!warning] 不要只搜索 § 符号
> 不同教材的节标题格式不同：
> - `§1.1 随机事件及其运算`（带 § 符号）
> - `1.1 随机事件及其运算`（纯数字编号）
> - `7.2 正态总体参数假设检验`（纯数字，无 §）

### 典型案例

| 小节 | 目录标注页码 | 实际标题页 | 偏差 |
|------|------------|-----------|------|
| §4.2 特征函数 | p194 | **p192** | -2页 |
| §5.4 三大抽样分布 | p251 | **p249** | -2页 |
| §6.2 矩估计及相合性 | p273 | **p272** | -1页 |

**规律：目录页码通常指向正文内容页，而非标题页。标题往往在前 1-2 页就出现了。**

---

## 八、核心分片脚本模板

### 模板 A：连续编页 PDF（有全局 OFFSET）

适用于：正常出版的教材，全书页码连续。

```python
#!/usr/bin/env python3
"""PDF 按小节拆分模板 A：连续编页 PDF（含重叠页策略）"""
import os, shutil
from pypdf import PdfReader, PdfWriter

INPUT_PDF = "输入PDF路径"
OUTPUT_DIR = "输出目录"
OFFSET = 22  # PDF页码 = 书籍页码 + OFFSET（必须验证！）

# 格式: (章节文件夹名, [(小节编号, 小节标题, 书籍起始页码), ...], 下一章起始页码)
CHAPTERS = [
    ("第1章_标题", [
        ("1.1", "小节标题", 书籍起始页码),
        ("1.2", "小节标题", 书籍起始页码),
    ], 下一章起始书页码),
]

AUXILIARY = [
    ("00_封面", 1, 2),           # (文件名, PDF起始页, PDF结束页)
    ("01_版权", 3, 5),
    ("02_前言", 6, 20),
    ("03_目录", 21, 26),
]

def split_pdf():
    reader = PdfReader(INPUT_PDF)
    total_pages = len(reader.pages)

    content_dir = os.path.join(OUTPUT_DIR, "章节内容")
    aux_dir = os.path.join(OUTPUT_DIR, "封面及辅助")
    os.makedirs(content_dir, exist_ok=True)
    os.makedirs(aux_dir, exist_ok=True)

    # === 辅助材料 ===
    for name, pdf_start, pdf_end in AUXILIARY:
        writer = PdfWriter()
        for i in range(pdf_start - 1, pdf_end):
            writer.add_page(reader.pages[i])
        with open(os.path.join(aux_dir, f"{name}.pdf"), "wb") as f:
            writer.write(f)

    # === 章节级 + 小节级分片 ===
    for ch_name, sections, next_ch_start in CHAPTERS:
        ch_dir = os.path.join(content_dir, ch_name)
        os.makedirs(ch_dir, exist_ok=True)

        # 章节级合订（含 overlap）
        ch_pdf_start = sections[0][2] + OFFSET - 1
        ch_pdf_end = next_ch_start + OFFSET - 1
        writer = PdfWriter()
        for i in range(ch_pdf_start, ch_pdf_end + 1):
            writer.add_page(reader.pages[i])
        with open(os.path.join(ch_dir, f"{ch_name}.pdf"), "wb") as f:
            writer.write(f)

        # 小节级（含 overlap）
        for i, (sec_num, sec_title, book_start) in enumerate(sections):
            if i + 1 < len(sections):
                book_end = sections[i + 1][2]  # 下一节起始页（overlap）
            else:
                book_end = next_ch_start  # 下一章起始页（overlap）

            pdf_start = book_start + OFFSET - 1
            pdf_end = book_end + OFFSET - 1
            page_count = pdf_end - pdf_start + 1

            # 安全检查（v4.0 增强）
            if page_count <= 0:
                print(f"  ⚠ {sec_num}_{sec_title}: {page_count}页（跳过）")
                continue
            if pdf_end >= total_pages:
                print(f"  ⚠ {sec_num}_{sec_title}: 越界 pdf_end={pdf_end}（截断）")
                pdf_end = total_pages - 1

            writer = PdfWriter()
            for page_idx in range(pdf_start, pdf_end + 1):
                writer.add_page(reader.pages[page_idx])
            with open(os.path.join(ch_dir, f"{sec_num}_{sec_title}.pdf"), "wb") as f:
                writer.write(f)
            print(f"  ✓ {sec_num}_{sec_title}.pdf (p{book_start}-{book_end}, {page_count}页)")

split_pdf()
```

### 模板 B：合并 PDF（无全局 OFFSET）

适用于：多个独立 PDF 合并的文件，每个子文件页码从 1 重新开始。

```python
#!/usr/bin/env python3
"""PDF 按小节拆分模板 B：合并 PDF（无全局 OFFSET，使用 PDF 绝对页码）"""
import os, shutil, re
from pypdf import PdfReader, PdfWriter

INPUT_PDF = "输入PDF路径"
OUTPUT_DIR = "输出目录"

# 页码是 PDF 绝对页码（1-based）
CHAPTERS = [
    ("第1章_标题", [
        ("1.1", "小节标题", 6),
        ("1.2", "小节标题", 19),
    ]),
]

def clean_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)

def split_pdf():
    reader = PdfReader(INPUT_PDF)
    total_pages = len(reader.pages)

    content_dir = os.path.join(OUTPUT_DIR, "章节内容")
    os.makedirs(content_dir, exist_ok=True)

    for ch_dir, sections in CHAPTERS:
        ch_out = os.path.join(content_dir, clean_filename(ch_dir))
        os.makedirs(ch_out, exist_ok=True)

        for i, (sec_num, sec_title, start_page) in enumerate(sections):
            if i + 1 < len(sections):
                end_page = sections[i + 1][2]
            else:
                end_page = total_pages  # 需根据实际情况调整

            pdf_start = start_page - 1
            pdf_end = min(end_page - 1, total_pages - 1)
            page_count = pdf_end - pdf_start + 1

            if page_count <= 0:
                continue

            writer = PdfWriter()
            for page_idx in range(pdf_start, pdf_end + 1):
                writer.add_page(reader.pages[page_idx])

            out_name = f"{sec_num}_{clean_filename(sec_title)}.pdf"
            with open(os.path.join(ch_out, out_name), "wb") as f:
                writer.write(f)

split_pdf()
```

### 模板 C：书签驱动分片（v4.0 新增）

适用于：有完整层级书签的 PDF（如算法导论、逻辑学导论）。

```python
#!/usr/bin/env python3
"""PDF 按书签拆分模板 C：基于书签的自动分片"""
import os, re
from pypdf import PdfReader, PdfWriter

INPUT_PDF = "输入PDF路径"
OUTPUT_DIR = "输出目录"

reader = PdfReader(INPUT_PDF)
outline = reader.outline

def clean(name):
    """清理书签标题：去除 null 字节和非法字符"""
    return re.sub(r'[<>:"/\\|?*\x00]', '', (name or "")).strip()

def parse_outline(items, level=0):
    """递归解析书签树，返回 (标题, 页码, 层级) 列表"""
    results = []
    for item in items:
        if isinstance(item, list):
            results.extend(parse_outline(item, level + 1))
        else:
            title = clean(item.title)
            if not title:
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
            except:
                continue
            results.append((title, page, level))
    return results

bookmarks = parse_outline(outline)

# 过滤：只取指定层级（如 level=0 为章，level=1 为节）
TARGET_LEVEL = 1  # 0=篇/章, 1=节
sections = [(t, p) for t, p, lv in bookmarks if lv == TARGET_LEVEL]

# 分片
for i, (title, start_page) in enumerate(sections):
    end_page = sections[i + 1][1] - 1 if i + 1 < len(sections) else len(reader.pages)
    # 跳过与下一节同页的书签（0页文件）
    if end_page < start_page:
        continue

    writer = PdfWriter()
    for p in range(start_page - 1, end_page):
        writer.add_page(reader.pages[p])
    with open(os.path.join(OUTPUT_DIR, f"{clean(title)}.pdf"), "wb") as f:
        writer.write(f)
    print(f"✓ {title}: p{start_page}-p{end_page} ({end_page-start_page+1}页)")
```

> [!note] 模板 C 的关键注意事项
> - **必须清理 null 字节**：某些 PDF 书签标题末尾有 `\x00`，会导致 `ValueError: embedded null byte`
> - **跳过同页书签**：父书签和子书签可能指向同一页，产生 0 页文件
> - **篇/章/节层级选择**：通过 `TARGET_LEVEL` 控制分片粒度

---

## 九、常见陷阱与解决方案

### 陷阱 1：书签中有冗余父节点

**表现**：如"正文"书签与"第一章"书签指向同一页，产生 0 页空文件。

**解决**：检测并跳过 0 页的书签，或手动定义章节列表。

### 陷阱 2：书签层级过深

**表现**：所有节和小节都在顶层（扁平书签），导致拆分出 50+ 个文件。

**解决**：只取章级别的书签进行分片，忽略节和小节书签。

### 陷阱 3：PDF 文本层乱码

**表现**：pypdf 能提取文本但全是乱码（特殊字体编码）。

**解决**：按扫描版处理，用 Read 工具或 OCR 识别。

### 陷阱 4：qpdf 对瘦身版 PDF 失败

**表现**：qpdf 报 offset 错误。

**解决**：改用 pypdf PdfWriter（性能稍差但兼容性好）。

### 陷阱 5：目录页码与实际标题页不一致

**表现**：目录写着 §4.2 从 p194 开始，但实际 p192 就有标题。

**解决**：以实际标题出现页为准。必须用 Read 工具逐页校验。

### 陷阱 6：比例估算页码误差大

**解决**：估算仅作初始值，必须用 Read 工具验证每个边界页。

### 陷阱 7：OCR 完全无法识别数学教材

**解决**：放弃 tesseract，直接用 Read 工具（视觉模型）逐页扫描。

### 陷阱 8：合并 PDF 独立编页

**识别**：查看多个章节起始页的底部页码，如果都显示 1，则为合并 PDF。

**解决**：放弃全局 OFFSET，使用模板 B。

### 陷阱 9：节标题格式多样

**解决**：同时识别 `§X.Y` 和纯数字 `X.Y` 格式。

### 陷阱 10：分片后验证发现边界错误

**解决**：验证不能只检查页数总和，**必须抽查分片文件的首页内容**。

### 陷阱 11：书签 null 字节导致崩溃（v4.0 新增）

**表现**：
```
ValueError: embedded null byte
```
当尝试用书签标题创建目录或文件名时触发。

**原因**：某些 PDF 的书签标题末尾有 `\x00`（null 字节），可能是 PDF 制作工具的 bug。

**实战案例**：《算法导论》全部 316 个书签都有尾部 `\x00`。

**解决**：
```python
title = (item.title or "").replace('\x00', '').strip()
# 或更彻底的清理：
title = re.sub(r'[\x00]', '', item.title or "")
```

### 陷阱 12：末节结束页设为 total_pages 导致海量重叠（v4.0 新增）

**表现**：分片脚本执行后，总页数远超原始 PDF（如 17022 页 vs 794 页）。

**原因**：每章最后一节的 `end_page` 被错误地设为 `total_pages`（PDF 总页数），导致该节延伸到全书末尾。如果有 234 个小节，每个都延伸到末尾，就会产生大量重叠。

**实战案例**：《算法导论》首次小节分片，234 节中有 39 个末节，每个都从自己的起始页延伸到 p794，导致总页数 17022。

**解决**：
```python
# ❌ 错误：末节延伸到 PDF 末尾
book_end = total_pages - OFFSET + 1

# ✅ 正确：末节延伸到下一章第一节起始页
if ch_idx + 1 < len(CHAPTERS):
    next_ch_first_sec = CHAPTERS[ch_idx + 1][1][0][2]
    book_end = next_ch_first_sec
else:
    book_end = known_end_page  # 如附录起始页
```

**通用防护**：在分片脚本中添加总页数合理性检查：
```python
expected_max = total_pages + len(sections) * 2  # 允许合理重叠
if total_split_pages > expected_max:
    print(f"⚠ 总页数异常: {total_split_pages} > 预期上限 {expected_max}")
```

### 陷阱 13：无用书签误导分片策略（v4.0 新增）

**表现**：PDF 有数百个书签，但全部是纯数字（如 1-75），无章节标题。

**原因**：PDF 制作工具（如 FreePic2Pdf）自动生成的页码书签。

**解决**：检测书签是否全部为纯数字，若是则忽略书签，使用 TOC 或文本提取方案（见 §2.6）。

### 陷阱 14：书签解析产生重复文件夹（v4.0 新增）

**表现**：输出目录中出现 `第10章 谓词逻辑：量化理论/` 和 `第10章_谓词逻辑/` 两个文件夹。

**原因**：书签中同一章节有不同标题（完整标题含副标题 vs 简短标题），解析时创建了两个文件夹。

**解决**：
1. 书签解析时，对同一章节的不同标题进行去重（取第一个或最短的）
2. 分片完成后，检查并合并重复文件夹
3. 文件夹名统一使用下划线（不用空格或冒号）

### 陷阱 15：篇首页/分隔页归属不清（v4.0 新增）

**表现**：PDF 中有"第一篇 基础篇"这样的篇首页，不知道归入哪一章。

**处理规则**：
- 篇首页（只有篇名，无正文）→ 归入辅助材料
- 篇首页后的空白页 → 归入辅助材料
- 第一章从篇首页之后正式开始

---

## 十、输出目录规范

```
书名_版次/
├── 章节内容/
│   ├── 第1章_标题/
│   │   ├── 第1章_标题.pdf          # 章节级合订
│   │   ├── 1.1_书名简写_小节标题.pdf  # 小节级
│   │   └── 1.2_书名简写_小节标题.pdf
│   └── 第2章_标题/
│       └── ...
└── 封面及辅助/
    ├── 00_封面及书名页.pdf
    ├── 01_版权及作者简介.pdf
    ├── 02_各版前言.pdf
    ├── 03_目录.pdf
    └── 04_附录.pdf
```

**命名规则**：
- 章节文件夹：`第X章_标题`（无空格，下划线连接）
- 小节文件：`编号_书名简写_标题.pdf`
- 封面及辅助：`编号_内容描述.pdf`（编号前导零对齐）

### 多书籍命名规范

> [!tip] 当处理多本书籍时，建议在小节文件名中加入书名简写前缀

```
# 单书籍（默认）
1.1_随机事件及其运算.pdf

# 多书籍（加书名简写）
1.1_卡方核心笔记_随机事件及其运算.pdf
1.1_数据库_数据库系统概述.pdf
1.1_习题解析_基本知识点.pdf
```

**好处**：
- 不同书籍的小节 PDF 可以混合存放在同一目录
- 文件管理器中按名称排序时，同一本书的小节自然聚在一起
- 避免不同书籍的同编号小节互相覆盖

---

## 十一、验证清单

- [ ] 输出文件数量与预期一致
- [ ] 每个文件非空（>0 页），无负数页
- [ ] **总页数合理性检查**：含重叠的总页数不应超过 `原始页数 + 小节数 × 2`（v4.0 新增）
- [ ] **抽查分片文件首页**：确认首页包含对应的章节/小节标题
- [ ] 抽查边界页：上一节末尾和下一节开头内容完整
- [ ] 无 0 页空文件
- [ ] 文件命名无非法字符（无 null 字节、无冒号、无空格）
- [ ] 偏移量已通过实际页面页码验证（建议两端验证）
- [ ] 无重复文件夹（v4.0 新增）

---

## 十二、工具依赖

| 工具 | 用途 | 安装 |
|------|------|------|
| pypdf | PDF 读取/写入/拆分 | `pip install pypdf` |
| pdf2image | PDF 页面转图片 | `pip install pdf2image` |
| poppler-utils | pdf2image 的后端（pdftoppm） | `apt install poppler-utils` |
| pytesseract | OCR 文字识别（效果差，不推荐用于数学教材） | `pip install pytesseract` |
| tesseract-ocr | OCR 引擎（需安装中文语言包） | `apt install tesseract-ocr tesseract-ocr-chi-sim` |
| Read 工具 | 视觉模型识别页面内容（**推荐**） | Trae 内置 |
| Task 工具 | 并行扫描多个章节 | Trae 内置 |

---

## 十三、Trae 部署细节（Agent 操作手册）

> [!important] 本章面向 Trae Agent
> 记录 Trae 作为 AI Agent 解决 PDF 分片问题时使用的工具编排策略、上下文管理、错误恢复流程和调试技巧。目的是让另一个 Trae 对话能高效复现整个工作流。

### 13.1 工具编排策略

#### 核心工具链

```
PDF 上传 → RunCommand(pypdf 探索) → RunCommand(pdf2image 转图) → Read(视觉识别)
                                                              ↓
                                                    确定结构/OFFSET
                                                              ↓
                                              RunCommand(分片脚本执行)
                                                              ↓
                                                    RunCommand(验证统计)
                                                              ↓
                                                    Read(抽查边界页)
```

#### 各工具的使用模式

| 工具 | 用途 | 使用模式 | 注意事项 |
|------|------|---------|---------|
| **Read** | 查看扫描版 PDF 页面内容 | `pdf2image` 转图片 → `Read(file_path, target="...")` | `target` 参数要明确描述期望看到的内容，提高识别准确率 |
| **RunCommand** | 执行 Python 脚本 | 将完整脚本通过 heredoc 写入再执行：`cat > script.py << 'EOF' ... EOF && python3 script.py` | 脚本必须自包含（所有数据硬编码），不依赖对话历史 |
| **Task(Explore)** | 并行扫描多章节 | 每个子代理负责 2-4 章的页面分析 | 最多同时 3 个子代理 |
| **Task(Plan)** | 制定分片计划 | 传入已收集的所有信息（OFFSET、章节结构、书签情况） | Plan 阶段只做只读操作 |
| **LS/Glob** | 检查目录结构 | 验证分片输出、查找文件 | `find . -name "*.pdf" \| wc -l` 统计文件数 |
| **Grep** | 搜索代码/文本 | 在脚本中查找特定模式 | 较少使用，PDF 分片主要不涉及代码搜索 |

#### 工具调用批量化原则

> [!tip] 独立操作必须并行发起
> 多个无依赖的 Read/RunCommand 调用应在同一消息中同时发出。

**典型并行场景：**

```python
# ✅ 正确：同时读取 4 个页面图片
Read(p021.png) + Read(p022.png) + Read(p023.png) + Read(p024.png)  # 同一消息

# ✅ 正确：同时转换页面并检查 PDF 信息
RunCommand(pdf2image 转图) + RunCommand(pypdf 读取书签)  # 同一消息

# ❌ 错误：逐个读取（浪费 4 轮对话）
Read(p021.png) → 等待 → Read(p022.png) → 等待 → ...
```

**不可并行的场景：**
- 后一步依赖前一步的结果（如先确定 OFFSET，再计算页码范围）
- 需要根据前一步的输出决定下一步操作

### 13.2 上下文窗口管理

#### 长对话的上下文压力

处理多本书籍后，对话历史会变得很长（每本书涉及：探索→计划→章节分片→小节分片→验证，约 20-30 轮工具调用）。上下文过长会导致：
- 响应变慢
- 早期信息可能被截断
- 后续书籍处理时可能遗忘前面的经验

#### 应对策略

**1. 脚本自包含**

所有分片数据（章节数据、OFFSET、页码范围）硬编码在 Python 脚本中，不依赖对话历史。即使上下文丢失，脚本仍可独立执行。

```python
# ✅ 自包含：所有数据在脚本内
CHAPTERS = [
    ("第1章_绪论", [("1.1", "数据库系统概述", 3), ...], 33),
    ...
]
OFFSET = 26
```

**2. 结构化摘要**

每本书处理完后，输出关键参数摘要，便于上下文切换时快速恢复：

```
关键参数：OFFSET=26, 18章92节, 书签无用, 扫描版
输出：/workspace/数据库系统概论_第6版/ (116文件, 106M)
```

**3. 中间文件管理**

| 目录 | 用途 | 生命周期 |
|------|------|---------|
| `/data/user/work/` | 临时文件：扫描图片、Python 脚本、验证图片 | 每本书处理后可清理 |
| `/workspace/` | 最终输出：分片后的 PDF 文件夹 | 持久保存 |
| `/workspace/.uploads/` | 用户上传的原始 PDF | 持久保存 |

**4. 临时文件命名规范**

```
/data/user/work/
├── db_scan/p021.png          # 扫描图片：{书名简写}_scan/p{页码}.png
├── db_offset/p029.png        # OFFSET验证图片
├── db_verify/xxx_p1.png      # 分片验证图片
├── db_split_chapters.py      # 章节分片脚本
├── db_split_sections.py      # 小节分片脚本
└── db2_split_all.py          # 合并执行脚本
```

### 13.3 错误恢复流程

#### 常见错误及恢复方案

| 错误 | 诊断方法 | 恢复方案 |
|------|---------|---------|
| `ValueError: embedded null byte` | 书签标题含 `\x00` | `.replace('\x00', '').strip()` |
| 总页数异常（如 17022 vs 794） | 末节 end_page 设为 total_pages | 末节 end_page = 下一章首节 start |
| 分片文件首页内容不对 | Read 抽查发现标题不匹配 | 修正该节 start_page，增量重跑 |
| `makedirs` 失败 | 文件名含非法字符（冒号、空格） | `re.sub(r'[<>:"/\\|?*]', '', name)` |
| 0 页空文件 | 书签父子节点同页 | 跳过 0 页书签 |
| 目录页找不到 | 前置页数估算错误 | 逐页向前/向后搜索 |
| Read 识别失败 | 图片 dpi 太低 | 提高 dpi（100→150→200） |

#### 增量修复策略

> [!tip] 发现错误后不要重跑全部，只修复出错的部分

**典型流程：**
1. 验证阶段发现第 3 章首页内容不对（显示的是第 2 章内容）
2. 定位问题：第 2 章的结束页码少算了 1 页
3. 修正数据：更新脚本中第 2 章的 end_page
4. 只重新执行第 2 章和第 3 章的分片（不重跑其他章节）
5. 重新验证这两个章节

#### 重复文件夹清理

当书签解析产生重复文件夹时（如 `第10章 谓词逻辑：量化理论/` 和 `第10章_谓词逻辑/`）：

```bash
# 1. 将重复文件夹中的文件移到正确文件夹
mv "重复文件夹"/*.pdf "正确文件夹"/
# 2. 删除空文件夹
rmdir "重复文件夹"
```

**预防措施：**
- 书签解析时对同一章节的不同标题进行去重
- 文件夹名统一使用下划线（不用空格或冒号）
- 篇标题页和附录归入辅助材料，不创建章节文件夹

### 13.4 调试技巧

#### 快速验证 OFFSET

```python
# 同时验证起始和末尾，两端确认
# 起始：PDF p29 = 书 p3 → OFFSET = 29 - 3 = 26
# 末尾：PDF p498 = 书 p472 → OFFSET = 498 - 472 = 26 ✓
# 如果两端不一致，说明中间可能有页码跳变
```

#### 总页数合理性检查

```python
# 分片脚本末尾添加
expected_max = total_pages + len(all_sections) * 2
if total_split_pages > expected_max:
    print(f"⚠ 异常！总页数 {total_split_pages} 超出预期上限 {expected_max}")
```

**判断标准：**
- 正常情况：`total_split ≈ original + sections_count`（每对相邻节共享 1 页）
- 异常情况：`total_split >> original`（如 17022 vs 794），说明有末节 bug

#### 边界页抽查策略

| 抽查对象 | 抽查数量 | 抽查方法 |
|---------|---------|---------|
| 每章首页 | 每章 1 个 | 转图片 → Read 确认章节标题 |
| 章节过渡处 | 全书 5-10 个 | 确认上一章末尾和下一章开头连续 |
| 随机小节 | 全书 3-5 个 | 确认小节标题与文件名匹配 |

#### 渐进式分片

```
步骤 1: 章节级分片（快速）
  → 验证 OFFSET 正确性
  → 验证章边界无遗漏
  → 发现问题及时修正

步骤 2: 小节级分片（精细）
  → 基于已验证的章边界
  → 逐章执行，每章执行后快速检查
```

**好处：** 章节级分片只需 10-20 秒，能快速发现 OFFSET 错误。如果在章节级就发现错误，避免在小节级浪费更多时间。

### 13.5 Plan Mode 工作流

#### 何时使用 Plan Mode

- **每本新书的第一步**：进入 Plan Mode，先探索 PDF 结构、确定分片方案
- **复杂决策点**：如发现合并 PDF、无用书签等特殊情况时

#### Plan 阶段操作规范

**只做只读操作：**
- ✅ `RunCommand` 读取 PDF 信息（pypdf 读取书签、页数）
- ✅ `RunCommand(pdf2image)` 转换页面为图片
- ✅ `Read` 查看图片内容
- ✅ `LS/Glob` 检查文件系统
- ❌ 不创建输出目录
- ❌ 不执行分片脚本
- ❌ 不修改任何文件（计划文件除外）

#### 计划文件规范

```
路径：/workspace/.trae/documents/$(unique_plan_title).md
命名：小写英文+连字符，如 db-split-plan.md
内容：摘要、当前状态分析、执行步骤、关键决策、预期输出
```

#### 计划批准后的执行流程

```
1. 读取计划文件（刷新上下文）
2. 创建 TodoList（跟踪进度）
3. 按步骤执行：
   a. 章节级分片 → 更新 Todo → 验证
   b. 小节级分片 → 更新 Todo → 验证
   c. 辅助材料分片 → 更新 Todo → 验证
4. 输出最终统计
```

### 13.6 性能优化

#### pdf2image 批量转换

```python
# ✅ 正确：一次转换 6 页
images = convert_from_path(pdf_path, first_page=6, last_page=11, dpi=150)
for i, img in enumerate(images):
    img.save(f"p{6+i}.png")

# ❌ 错误：逐页转换 6 次
for p in range(6, 12):
    images = convert_from_path(pdf_path, first_page=p, last_page=p, dpi=150)
    images[0].save(f"p{p}.png")
```

**性能差异**：批量转换比逐页快 3-5 倍（poppler 的 pdftoppm 启动开销）。

#### 脚本合并执行

将章节级、小节级、辅助材料分片合并在一个 Python 脚本中执行，减少工具调用次数：

```python
# 一个脚本完成所有分片
def split_all():
    split_auxiliary()      # 辅助材料
    split_chapters()       # 章节级
    split_sections()       # 小节级
    print_summary()        # 统计输出
```

**好处**：从 3 次 RunCommand 减少到 1 次，且脚本内部可以共享 PdfReader 对象。

#### dpi 选择策略

| 用途 | 推荐 dpi | 原因 |
|------|---------|------|
| 粗扫定位（两阶段采样法阶段一） | 100 | 速度快，只需识别大致内容 |
| 精确定位标题页 | 150 | 平衡速度和清晰度 |
| 验证分片结果 | 100-150 | 只需确认标题文字 |
| OCR 识别 | 200 | 需要最高清晰度 |

#### 大文件处理

对于 1000+ 页的 PDF（如逻辑学导论 1222 页）：
- 分片脚本执行时间约 30-60 秒，需设置合适的超时
- 避免一次性转换太多页面图片（每次最多 20-30 页）
- 书签解析和文本提取比图片转换快得多，优先使用

### 13.7 环境约束

#### 文件系统

| 路径 | 用途 | 权限 |
|------|------|------|
| `/workspace/` | 最终输出目录，用户可见 | 读写 |
| `/workspace/.uploads/` | 用户上传的原始 PDF | 只读 |
| `/data/user/work/` | 临时工作目录，用户不可见 | 读写 |

#### Python 环境

```
Python: 3.10
pypdf: 3.17.4
pdf2image: 已安装
poppler-utils: 已安装 (pdftoppm)
pytesseract: 已安装 (但不推荐用于数学教材)
tesseract: 4.1.1 (chi_sim+eng)
```

#### 常用命令

```bash
# pip 安装（必须加 --break-system-packages）
pip install xxx --break-system-packages

# PDF 信息查看
python3 -c "from pypdf import PdfReader; r=PdfReader('xxx.pdf'); print(len(r.pages))"

# 页面转图片
python3 -c "from pdf2image import convert_from_path; convert_from_path('xxx.pdf', first_page=1, last_page=5, dpi=150)[0].save('p1.png')"

# 文件统计
find /workspace/xxx -name "*.pdf" | wc -l
du -sh /workspace/xxx
```

#### 已知限制

| 限制 | 影响 | 应对 |
|------|------|------|
| 命令默认超时 2 分钟 | 大文件分片可能超时 | 脚本内部分批处理 |
| Task 子代理最多 3 个 | 并行扫描受限 | 合理分组 |
| Read 工具单次一张图 | 批量查看需多次调用 | 并行发起多个 Read |
| 上下文窗口有限 | 长对话可能截断 | 脚本自包含 + 结构化摘要 |
| `/data/user/work/` 不持久 | 会话间重置 | 最终输出必须存到 `/workspace/` |

---

## 十四、已处理书籍清单

| # | 书名 | 总页数 | 分片粒度 | 偏移量 | 页码来源 | PDF类型 | 输出文件数 | 大小 |
|---|------|--------|---------|--------|---------|---------|-----------|------|
| 1 | 傅里叶分析 (Stein) | 227 | 按章 | — | 书签直读 | 文本版 | — | — |
| 2 | 泛函分析 (Stein) | 332 | 按章 | +10 | 书签直读 | 文本版 | — | — |
| 3 | 泛函分析讲义 (张恭庆) | 330+333 | 按章 | — | 书签直读 | 文本版 | — | — |
| 4 | 概率论与数理统计教程 (茆诗松第三版) | 490 | 按小节(43) | +22 | OCR目录+Read校验 | 扫描版 | — | — |
| 5 | 概率论与数理统计教程习题与解答 | 462 | 按小节(43) | +5 | OCR目录 | 扫描版 | — | — |
| 6 | 五三解析册 (卡方) | 444 | 按小节(26) | +5 | OCR目录 | 扫描版 | — | — |
| 7 | 五三刷题册 (卡方) | 499 | 按小节(26) | +5 | OCR目录 | 扫描版 | — | — |
| 8 | 核心笔记/讲义 (卡方茆诗松) | 378 | 按小节(43) | 无（合并PDF） | Read逐页扫描 | 扫描版 | 47 | 119M |
| 9 | 算法导论 第三版 (CLRS) | 794 | 按小节(234) | — | 书签(316个,4级) | 文本版 | 238 | 109M |
| 10 | Modern Operating Systems 5th | 1185 | 按小节(110) | — | 书签(492个,3级) | 扫描版 | 113 | 119M |
| 11 | 数据库系统概论 第6版 | 500 | 按小节(92) | +26 | TOC手动(书签无用) | 扫描版 | 116 | 106M |
| 12 | 数据库习题解析 第6版 | 296 | 按小节(58) | +15 | TOC手动(无书签) | 扫描版 | 80 | 29M |
| 13 | 逻辑学导论 第15版 | 1222 | 按小节(90) | — | 书签+文本正则 | 文本版 | 122 | 222M |
| 14 | 逻辑学导论 第15版 (柯匹) | 1222 | 按小节(90) | — | 书签+文本正则 | 文本版 | 122 | 222M |

> [!note] 部署概况（截至 v4.0）
> - 已完成分片的书籍：**6 本**（#8-#13），共 **716 个 PDF 文件**，总计约 **704M**
> - 涵盖 PDF 类型：扫描版(4本)、文本版(2本)、合并PDF(1本)
> - 涵盖书签情况：完整书签(3本)、无用书签(1本)、无书签(2本)
> - 详细的 Agent 操作部署细节见 **§十三**

---

## 附录 A：实战记录 — 算法导论分片（v4.0 新增）

### 基本信息

- **PDF**：Introduction to Algorithms (CLRS) 3rd Edition
- **总页数**：794 页
- **PDF 类型**：文本版（可选择文本）
- **书签**：316 个，4 级层级（L0:14, L1:35, L2:234, L3:29）

### 遇到的问题

#### 问题 1：书签 null 字节

全部 316 个书签标题末尾有 `\x00`，导致 `makedirs()` 报 `ValueError: embedded null byte`。

**修复**：`title = (item.title or "").replace('\x00', '').strip()`

#### 问题 2：末节结束页 bug

首次小节分片产生 17022 页（原始仅 794 页）。原因：每章最后一节的 `end_page` 被设为 `total_pages`。

**修复**：末节结束页 = 下一章第一节起始页，而非 PDF 总页数。

### 最终结果

- 238 个文件（234 小节 + 4 辅助）
- 39 个章节文件夹

---

## 附录 B：实战记录 — 数据库系统概论分片（v4.0 新增）

### 基本信息

- **PDF**：数据库系统概论 第6版（王珊等）
- **总页数**：500 页
- **PDF 类型**：扫描版（FreePic2Pdf），无文本层
- **书签**：478 个但全部无用（仅数字 1-75）

### 特殊处理

1. **无用书签检测**：全部书签为纯数字，忽略书签
2. **TOC 手动构建**：用 Read 工具扫描目录页（p21-p26），提取 4 篇 18 章 92 小节的完整结构
3. **双重 OFFSET 验证**：PDF p29=书p3(起始)，PDF p498=书p472(末尾)，OFFSET=26 两端一致

### 最终结果

- 116 个文件（18 章节 + 92 小节 + 6 辅助）
- 18 个章节文件夹

---

## 附录 C：实战记录 — 逻辑学导论分片（v4.0 新增）

### 基本信息

- **PDF**：逻辑学导论 第15版（柯匹）
- **总页数**：1222 页
- **PDF 类型**：文本版（可选择文本）
- **书签**：完整层级结构（篇→章→节）

### 特殊处理

1. **文本层正则提取节标题**：用 `re.match(r'^(\d+\.\d+)\s+(.{2,40})$', line)` 自动提取 90 个小节标题
2. **误匹配过滤**：过滤掉章节小结行（如 `1.1 节 说明什么是逻辑学...`）
3. **重复文件夹清理**：书签中的完整标题（含副标题）和章节级分片产生的简短标题创建了重复文件夹，需合并

### 最终结果

- 122 个文件（14 章节 + 90 小节 + 18 辅助）
- 14 个章节文件夹
