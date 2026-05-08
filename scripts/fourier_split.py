#!/usr/bin/env python3
"""
傅里叶分析 (Stein & Shakarchi) - 小节级分片脚本

纯扫描版 PDF（227页），无书签页码，无文本层。
通过 Read 工具逐页扫描确定小节起始页，硬编码到脚本中。

特点：
  - 按小节（x.y）粒度拆分，共 46 个小节
  - 小节归入对应章节文件夹
  - 零填充编号（01.01_弦振动, 01.02_热传导方程, ...）
  - 同章小节间 1 页重叠，跨章精确切割
"""
import os
import re
import csv
from pypdf import PdfReader, PdfWriter

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/444d72bb-a59b-4a38-b949-7cae7276fb47_(已瘦身)傅里叶分析 (Elias M. Stein,Rami Shakarchi) (Z-Library).pdf"
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

# 小节起始页（硬编码，来自逐页扫描精确定位）
# 格式: (小节编号, 标题, PDF起始页, 所属章节号, 类型)
# 类型: "内容" / "练习" / "问题"
SECTIONS = [
    # 第1章 Fourier分析的起源
    ("1.1", "弦振动", 12, 1, "内容"),
    ("1.2", "热传导方程", 24, 1, "内容"),
    ("1.3", "练习", 26, 1, "练习"),
    ("1.4", "问题", 30, 1, "问题"),
    # 第2章 Fourier级数的基本性质
    ("2.1", "问题的例子和公式", 32, 2, "内容"),
    ("2.2", "Fourier级数的唯一性", 38, 2, "内容"),
    ("2.3", "卷积", 40, 2, "内容"),
    ("2.4", "好核", 42, 2, "内容"),
    ("2.5", "Cesaro和Abel求和", 47, 2, "内容"),
    ("2.6", "练习", 50, 2, "练习"),
    ("2.7", "问题", 56, 2, "问题"),
    # 第3章 Fourier级数的收敛性
    ("3.1", "Fourier级数的均方收敛", 61, 3, "内容"),
    ("3.2", "逐点收敛", 70, 3, "内容"),
    ("3.3", "练习", 72, 3, "练习"),
    ("3.4", "问题", 78, 3, "问题"),
    # 第4章 Fourier级数的一些应用
    ("4.1", "等周不等式", 82, 4, "内容"),
    ("4.2", "Weyl等分布定理", 85, 4, "内容"),
    ("4.3", "处处不可微的连续函数", 90, 4, "内容"),
    ("4.4", "圆上的热方程", 93, 4, "内容"),
    ("4.5", "练习", 95, 4, "练习"),
    ("4.6", "问题", 98, 4, "问题"),
    # 第5章 R上的Fourier变换
    ("5.1", "Fourier变换的基本理论", 102, 5, "内容"),
    ("5.2", "偏微分方程中的一些应用", 114, 5, "内容"),
    ("5.3", "Poisson求和公式", 118, 5, "内容"),
    ("5.4", "Heisenberg不确定性原理", 122, 5, "内容"),
    ("5.5", "练习", 124, 5, "练习"),
    ("5.6", "问题", 132, 5, "问题"),
    # 第6章 R_d上的Fourier变换
    ("6.1", "预备知识", 137, 6, "内容"),
    ("6.2", "Fourier变换的初等理论", 140, 6, "内容"),
    ("6.3", "R_d_x_R上的波动方程", 143, 6, "内容"),
    ("6.4", "径向对称与Bessel函数", 152, 6, "内容"),
    ("6.5", "Radon变换及其应用", 155, 6, "内容"),
    ("6.6", "练习", 158, 6, "练习"),
    ("6.7", "问题", 162, 6, "问题"),
    # 第7章 有限Fourier分析
    ("7.1", "Z_N上的Fourier分析", 167, 7, "内容"),
    ("7.2", "有限Abel群上的Fourier分析", 172, 7, "内容"),
    ("7.3", "练习", 178, 7, "练习"),
    ("7.4", "问题", 181, 7, "问题"),
    # 第8章 Dirichlet定理
    ("8.1", "一些基本的数论知识", 183, 8, "内容"),
    ("8.2", "Dirichlet定理", 190, 8, "内容"),
    ("8.3", "Dirichlet定理的证明", 195, 8, "内容"),
    ("8.4", "练习", 208, 8, "练习"),
    ("8.5", "问题", 210, 8, "问题"),
    # 第9章 积分
    ("9.1", "Riemann可积函数的定义", 212, 9, "内容"),
    ("9.2", "多重积分", 218, 9, "内容"),
    ("9.3", "反常积分_R_d上的积分", 222, 9, "内容"),
]

# 章节标题
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
    name = name.replace('^', '_d_')
    name = re.sub(r'\s+', '_', name.strip())
    return name


def chapter_dir_name(ch_num):
    """生成章节目录名"""
    title = CHAPTER_TITLES.get(ch_num, "")
    return f"{ch_num:02d}_第{ch_num}章_{sanitize(title)}"


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

    # 小节
    for i, (sec_id, title, page, ch_num, sec_type) in enumerate(SECTIONS):
        # 结束页：下一个小节起始页 - 1（同章1页重叠，跨章精确切割）
        if i + 1 < len(SECTIONS):
            next_page = SECTIONS[i + 1][2]
            next_ch = SECTIONS[i + 1][3]
            if next_ch == ch_num:
                end_page = next_page  # 同章：1页重叠
            else:
                end_page = next_page - 1  # 跨章：精确切割
        else:
            end_page = 225  # 参考文献前

        if end_page < page:
            continue

        ch_dir = chapter_dir_name(ch_num)
        file_name = f"{sec_id}_{sanitize(title)}.pdf"

        chunks.append({
            "title": f"{sec_id}_{title}",
            "start": page, "end": end_page,
            "dir": ch_dir, "filename": file_name,
            "category": sec_type,
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
    print("傅里叶分析 - 小节级分片")
    print("=" * 60)

    print(f"\n[1] PDF信息: {TOTAL_PAGES} 页, {len(SECTIONS)} 小节")

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
        print(f"页数差异: {total_pages - TOTAL_PAGES} (含重叠)")
    print(f"{'='*60}")

    csv_path = os.path.join(OUTPUT_ROOT, "分片清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["序号","类别","标题","起始页","结束页","页数","相对路径"])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\n分片清单: {csv_path}")


if __name__ == "__main__":
    main()
