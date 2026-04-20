#!/usr/bin/env python3
"""
泛函分析 (Stein & Shakarchi) - 小节级分片脚本

纯扫描版 PDF（332页），无文本层。
通过 Read 工具逐页扫描确定小节起始页，硬编码到脚本中。

注意：目录给出的页码与实际严重不符，以下起始页均为实际扫描确认。
PDF页码 = 书籍页码 + 10

特点：
  - 按一级小节（x.y）拆分，不拆分子小节（x.y.z）
  - 小节归入对应章节文件夹
  - 零填充编号（1.1_标题, 1.2_标题, ...）
  - 同章小节间 1 页重叠，跨章精确切割
"""
import os
import re
import csv
from pypdf import PdfReader, PdfWriter

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/39a5c890-38e8-429d-bb90-f5947ba5452e_(已瘦身)泛函分析 ( etc.) (Z-Library).pdf"
OUTPUT_ROOT = "/workspace/泛函分析"
TOTAL_PAGES = 332

# 辅助材料：(文件名, PDF起始页, PDF结束页)
AUXILIARY = [
    ("封面", 1, 10),
    ("注记和参考", 325, 327),
    ("参考文献", 328, 330),
    ("符号表", 331, 332),
]

# 小节起始页（硬编码，来自逐页扫描确认）
# 格式: (小节编号, 标题, PDF起始页, 所属章节号, 类型)
# 类型: "内容" / "习题" / "问题"
SECTIONS = [
    # 第1章 L^p空间和Banach空间 (PDF p11-p45)
    ("1.1", "L_p空间", 11, 1, "内容"),
    ("1.2", "L_无穷空间", 16, 1, "内容"),
    ("1.3", "Banach空间", 21, 1, "内容"),
    ("1.4", "L_p的对偶空间", 26, 1, "内容"),
    ("1.6", "复L_p空间和Banach空间", 29, 1, "内容"),
    ("1.5", "Hahn-Banach定理", 31, 1, "内容"),
    ("1.7", "附录_C_X_的对偶空间", 41, 1, "内容"),
    ("1.8", "习题", 46, 1, "习题"),
    ("1.9", "问题", 48, 1, "问题"),
    # 第2章 调和分析中的L^p空间 (PDF p46-p84)
    ("2.1", "早期动机", 47, 2, "内容"),
    ("2.2", "Riesz内插定理", 49, 2, "内容"),
    ("2.3", "Hilbert变换的L_p理论", 56, 2, "内容"),
    ("2.4", "极大函数和弱型估计", 62, 2, "内容"),
    ("2.5", "Hardy空间H_1_r", 66, 2, "内容"),
    ("2.6", "空间H_1_r和极大函数", 73, 2, "内容"),
    ("2.7", "习题", 79, 2, "习题"),
    ("2.8", "问题", 82, 2, "问题"),
    # 第3章 分布：广义函数 (PDF p85-p129)
    ("3.1", "基本性质", 86, 3, "内容"),
    ("3.2", "广义函数的重要例子", 95, 3, "内容"),
    ("3.3", "Calderon-Zygmund分布及L_p估计", 115, 3, "内容"),
    ("3.4", "习题", 120, 3, "习题"),
    ("3.5", "问题", 126, 3, "问题"),
    # 第4章 Baire纲定理的应用 (PDF p130-p151)
    ("4.1", "Baire纲定理", 131, 4, "内容"),
    ("4.2", "一致有界原理", 136, 4, "内容"),
    ("4.3", "开映射定理", 139, 4, "内容"),
    ("4.4", "闭图像定理", 142, 4, "内容"),
    ("4.5", "Besicovitch集", 145, 4, "内容"),
    ("4.6", "习题", 147, 4, "习题"),
    ("4.7", "问题", 150, 4, "问题"),
    # 第5章 概率论基础 (PDF p152-p191)
    ("5.1", "Bernoulli试验", 153, 5, "内容"),
    ("5.2", "独立随机变量的和", 167, 5, "内容"),
    ("5.3", "习题", 182, 5, "习题"),
    ("5.4", "问题", 189, 5, "问题"),
    # 第6章 Brownian运动引论 (PDF p192-p220)
    ("6.1", "框架", 193, 6, "内容"),
    ("6.2", "技巧准备", 194, 6, "内容"),
    ("6.3", "Brownian运动的构造", 198, 6, "内容"),
    ("6.4", "Brownian运动的进一步的性质", 201, 6, "内容"),
    ("6.5", "停时和强Markov性质", 207, 6, "内容"),
    ("6.6", "Dirichlet问题的解", 211, 6, "内容"),
    ("6.7", "习题", 215, 6, "习题"),
    ("6.8", "问题", 218, 6, "问题"),
    # 第7章 多复变引论 (PDF p221-p246)
    ("7.1", "初等性质", 222, 7, "内容"),
    ("7.2", "Hartogs现象_一个例子", 224, 7, "内容"),
    ("7.3", "Hartogs定理_非齐次Cauchy-Riemann方程", 226, 7, "内容"),
    ("7.4", "边界情形_切向Cauchy-Riemann方程", 231, 7, "内容"),
    ("7.5", "Levi形式", 235, 7, "内容"),
    ("7.6", "最大模原理", 236, 7, "内容"),
    ("7.7", "逼近和延拓定理", 238, 7, "内容"),
    ("7.8", "附录_上半空间", 244, 7, "内容"),
    ("7.9", "习题", 251, 7, "习题"),
    # 第8章 Fourier分析中的振荡积分 (PDF p247-p324)
    ("8.1", "一个例证", 258, 8, "内容"),
    ("8.2", "振荡积分", 260, 8, "内容"),
    ("8.3", "支撑曲面测度的Fourier变换", 267, 8, "内容"),
    ("8.4", "回到平均算子", 269, 8, "内容"),
    ("8.5", "限制定理", 274, 8, "内容"),
    ("8.6", "对一些色散方程的应用", 277, 8, "内容"),
    ("8.7", "Radon变换", 287, 8, "内容"),
    ("8.8", "格点计数", 302, 8, "内容"),
    ("8.9", "习题", 312, 8, "习题"),
    ("8.10", "问题", 317, 8, "问题"),
]

# 章节标题
CHAPTER_TITLES = {
    1: "L_p空间和Banach空间",
    2: "调和分析中的L_p空间",
    3: "分布_广义函数",
    4: "Baire纲定理的应用",
    5: "概率论基础",
    6: "Brownian运动引论",
    7: "多复变引论",
    8: "Fourier分析中的振荡积分",
}

# ==================== 工具函数 ====================

def sanitize(title):
    """清理标题为合法文件名"""
    name = title.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('—', '-')
    name = name.replace('#', '_sharp_')
    name = name.replace('^', '_p_')
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
        # 结束页
        if i + 1 < len(SECTIONS):
            next_page = SECTIONS[i + 1][2]
            next_ch = SECTIONS[i + 1][3]
            if next_ch == ch_num:
                end_page = next_page  # 同章：1页重叠
            else:
                end_page = next_page - 1  # 跨章：精确切割
        else:
            end_page = 324  # 注记和参考前

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
    print("泛函分析 - 小节级分片")
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
