#!/usr/bin/env python3
"""
傅里叶分析 (Stein & Shakarchi) - 章节级分片脚本

纯扫描版 PDF（227页），无书签页码，无文本层。
通过 Read 工具逐页扫描确定章节起始页，硬编码到脚本中。

特点：
  - 按章节拆分，共 9 章 + 辅助材料
  - 零填充编号（01_第1章, 02_第2章, ...）
  - 同章 1 页重叠，跨章精确切割
"""
import os
import re
import csv
from pypdf import PdfReader, PdfWriter

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/b3982d9d-28bb-4660-a1ce-22f96f00bec2_傅里叶分析 (Elias M. Stein,Rami Shakarchi) (Z-Library).pdf"
OUTPUT_ROOT = "/workspace/傅里叶分析"
TOTAL_PAGES = 227

# 辅助材料：(文件名, PDF起始页, PDF结束页)
AUXILIARY = [
    ("封面", 1, 4),
    ("前言", 5, 6),
    ("引言", 7, 7),
    ("目录", 8, 11),
    ("参考文献", 226, 227),
]

# 章节起始页（硬编码，来自 Read 工具逐页扫描）
# PDF页码 = 书籍页码 + 11
CHAPTER_PAGES = {
    1: 12,   # Fourier分析的起源
    2: 30,   # Fourier级数的基本性质
    3: 58,   # Fourier级数的收敛性
    4: 82,   # Fourier级数的一些应用
    5: 102,  # R上的Fourier变换
    6: 136,  # R^d上的Fourier变换
    7: 166,  # 有限Fourier分析
    8: 182,  # Dirichlet定理
    9: 212,  # 积分
}

CHAPTER_TITLES = {
    1: "Fourier分析的起源",
    2: "Fourier级数的基本性质",
    3: "Fourier级数的收敛性",
    4: "Fourier级数的一些应用",
    5: "R上的Fourier变换",
    6: "R_d上的Fourier变换",
    7: "有限Fourier分析",
    8: "Dirichlet定理",
    9: "积分",
}

# ==================== 工具函数 ====================

def sanitize(title):
    """清理标题为合法文件名"""
    name = title.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('—', '-')
    name = name.replace('#', '_sharp_')
    name = name.replace('^', '_d_')  # R^d → R_d
    name = re.sub(r'\s+', '_', name.strip())
    return name


# ==================== 分片列表构建 ====================

def build_chunks():
    """构建完整分片列表"""
    chunks = []

    # 辅助材料
    for name, start, end in AUXILIARY:
        chunks.append({
            "title": name, "start": start, "end": end,
            "dir": "00_辅助材料", "filename": f"{sanitize(name)}.pdf",
            "category": "辅助材料",
        })

    # 章节
    sorted_chs = sorted(CHAPTER_PAGES.keys())
    for i, ch_num in enumerate(sorted_chs):
        page = CHAPTER_PAGES[ch_num]
        title = CHAPTER_TITLES.get(ch_num, f"第{ch_num}章")

        # 结束页
        if i + 1 < len(sorted_chs):
            next_page = CHAPTER_PAGES[sorted_chs[i + 1]]
            end_page = next_page - 1  # 跨章精确切割
        else:
            end_page = 225  # 参考文献前

        if end_page < page:
            continue

        dir_name = f"{ch_num:02d}_第{ch_num}章_{sanitize(title)}"
        file_name = f"{ch_num:02d}_第{ch_num}章_{sanitize(title)}.pdf"

        chunks.append({
            "title": f"第{ch_num}章_{title}",
            "start": page, "end": end_page,
            "dir": dir_name, "filename": file_name,
            "category": "章节",
        })

    return chunks


# ==================== 分片执行 ====================

def execute_split(chunks):
    """执行 PDF 分片"""
    reader = PdfReader(INPUT_PDF)
    total_pages = 0
    file_count = 0
    csv_rows = []

    for chunk in chunks:
        start = chunk["start"]
        end = chunk["end"]
        if end < start:
            continue

        page_count = end - start + 1
        out_dir = os.path.join(OUTPUT_ROOT, chunk["dir"])
        os.makedirs(out_dir, exist_ok=True)

        writer = PdfWriter()
        for p in range(start - 1, end):
            writer.add_page(reader.pages[p])

        out_path = os.path.join(out_dir, chunk["filename"])
        with open(out_path, "wb") as f:
            writer.write(f)

        total_pages += page_count
        file_count += 1
        rel_path = os.path.join(chunk["dir"], chunk["filename"])

        csv_rows.append({
            "序号": file_count, "类别": chunk["category"],
            "标题": chunk["title"], "起始页": start, "结束页": end,
            "页数": page_count, "相对路径": rel_path,
        })
        print(f"  [{file_count:3d}] {rel_path} (p{start}-p{end}, {page_count}p)")

    return file_count, total_pages, csv_rows


# ==================== 主流程 ====================

def main():
    print("=" * 60)
    print("傅里叶分析 - 章节级分片")
    print("=" * 60)

    print(f"\n[1] PDF信息: {TOTAL_PAGES} 页, {len(CHAPTER_PAGES)} 章")

    print("\n[2] 构建分片列表...")
    chunks = build_chunks()
    print(f"  分片条目: {len(chunks)}")

    print(f"\n[3] 执行分片 -> {OUTPUT_ROOT}")
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    file_count, total_pages, csv_rows = execute_split(chunks)

    print(f"\n{'='*60}")
    print(f"原始 PDF: {TOTAL_PAGES} 页")
    print(f"分片文件: {file_count} 个, 共 {total_pages} 页")
    if total_pages == TOTAL_PAGES:
        print(f"页数守恒 ✓")
    else:
        print(f"页数差异: {total_pages - TOTAL_PAGES}")
    print(f"{'='*60}")

    csv_path = os.path.join(OUTPUT_ROOT, "分片清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["序号","类别","标题","起始页","结束页","页数","相对路径"])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\n分片清单: {csv_path}")


if __name__ == "__main__":
    main()
