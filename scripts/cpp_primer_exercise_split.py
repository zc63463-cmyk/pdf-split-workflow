#!/usr/bin/env python3
"""
C++ Primer 习题集 - 章节级分片脚本
528页，纯扫描版，23个章节级书签
按章节拆分（习题集无小节标题，无法按小节分片）
"""
import os
import re
import csv
from pypdf import PdfReader, PdfWriter

# ============ 配置 ============
INPUT_PDF = "/workspace/.uploads/95a160eb-48d5-4ef4-97e9-136c97774130_C++ PRIMER习题集 (Stanley B.Lippman, Josee Lajoie, Barbara E.Moo).pdf"
OUTPUT_ROOT = "/workspace/C++_Primer_习题集"
TOTAL_PAGES = 528

# ============ 辅助材料 ============
AUXILIARY = [
    ("00_封面与书名", 1, 2),
    ("01_版权", 3, 3),
    ("02_前言", 4, 4),
    ("03_目录", 5, 6),
]

# ============ 章节数据 ============
# 格式: (章节编号, 标题, PDF起始页, 习题范围)
CHAPTERS = [
    (1, "开始", 7, "练习1~25"),
    (2, "变量和基本类型", 18, "练习1~42"),
    (3, "字符串_向量和数组", 43, "练习1~45"),
    (4, "表达式", 86, "练习1~38"),
    (5, "语句", 105, "练习1~25"),
    (6, "函数", 126, "练习1~56"),
    (7, "类", 158, "练习1~58"),
    (8, "IO库", 189, "练习8.1~14"),
    (9, "顺序容器", 199, "练习1~52"),
    (10, "泛型算法", 240, "练习1~42"),
    (11, "关联容器", 279, "练习1~38"),
    (12, "动态内存", 303, "练习1~33"),
    (13, "拷贝控制", 337, "练习1~58"),
    (14, "重载运算与类型转换", 374, "练习1~53"),
    (15, "面向对象程序设计", 405, "练习1~42"),
    (16, "模板与泛型编程", 430, "练习1~67"),
    (17, "标准库特殊设施", 464, "练习1~39"),
    (18, "用于大型程序的工具", 489, "练习1~30"),
    (19, "特殊工具与技术", 508, "练习1~26"),
]

# 封底
BACK_COVER = ("20_封底", 527, 528)


def sanitize(title):
    """清理标题用于文件名"""
    name = title.replace('\x00', '')
    name = name.replace('++', '_plusplus_')
    name = name.replace('->', '_arrow_')
    name = name.replace('::', '_scope_')
    name = name.replace('#', '_sharp_')
    name = name.replace('*', '_star_')
    name = name.replace('<', '_lt_').replace('>', '_gt_')
    name = name.replace('+', '_plus_')
    name = name.replace('=', '_eq_')
    name = name.replace('&', '_and_')
    name = name.replace('|', '_or_')
    name = name.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('"', '').replace('"', '')
    name = name.replace('—', '-').replace('–', '-')
    name = name.replace('（', '').replace('）', '')
    name = name.replace('，', '_').replace('：', '_').replace('；', '_')
    name = name.replace('(', '').replace(')', '')
    name = name.replace('[', '').replace(']', '')
    name = name.replace('{', '').replace('}', '')
    name = name.replace("'", '').replace('"', '')
    name = name.replace(',', '_')
    name = name.replace(' ', '_')
    name = name.strip().strip('_')
    name = re.sub(r'_+', '_', name)
    return name


def build_chunks():
    """构建分片列表"""
    chunks = []

    # 辅助材料
    for name, start, end in AUXILIARY:
        chunks.append({
            "title": name,
            "start": start,
            "end": end,
            "dir": "00_辅助材料",
            "filename": f"{name}.pdf",
            "category": "辅助材料",
        })

    # 章节分片（跨章精确切割，无重叠）
    for i, (ch_num, title, start_page, ex_range) in enumerate(CHAPTERS):
        if i + 1 < len(CHAPTERS):
            end_page = CHAPTERS[i + 1][2] - 1  # 跨章精确切割
        else:
            end_page = BACK_COVER[1] - 1  # 最后一章到封底前一页

        ch_dir = f"{ch_num:02d}_{sanitize(title)}"
        file_name = f"{ch_num:02d}_{sanitize(title)}.pdf"

        chunks.append({
            "title": f"第{ch_num}章 {title} ({ex_range})",
            "start": start_page,
            "end": end_page,
            "dir": ch_dir,
            "filename": file_name,
            "category": "内容",
        })

    # 封底
    chunks.append({
        "title": BACK_COVER[0],
        "start": BACK_COVER[1],
        "end": BACK_COVER[2],
        "dir": "00_辅助材料",
        "filename": f"{BACK_COVER[0]}.pdf",
        "category": "辅助材料",
    })

    return chunks


def execute_split(chunks):
    """执行分片"""
    reader = PdfReader(INPUT_PDF)
    file_count = 0
    total_split_pages = 0
    csv_rows = []

    for chunk in chunks:
        out_dir = os.path.join(OUTPUT_ROOT, chunk["dir"])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, chunk["filename"])

        writer = PdfWriter()
        page_count = 0
        for p in range(chunk["start"], chunk["end"] + 1):
            writer.add_page(reader.pages[p - 1])
            page_count += 1

        with open(out_path, "wb") as f:
            writer.write(f)

        file_count += 1
        total_split_pages += page_count
        csv_rows.append([
            chunk["dir"],
            chunk["filename"],
            chunk["title"],
            chunk["start"],
            chunk["end"],
            page_count,
            chunk["category"],
        ])
        print(f"  [{file_count:2d}] {chunk['dir']}/{chunk['filename']} "
              f"(p{chunk['start']}-p{chunk['end']}, {page_count}页)")

    csv_path = os.path.join(OUTPUT_ROOT, "分片清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["目录", "文件名", "标题", "起始页", "结束页", "页数", "类型"])
        writer.writerows(csv_rows)

    return file_count, total_split_pages


def main():
    print(f"[1] PDF信息: {TOTAL_PAGES}页, {len(CHAPTERS)}章")

    chunks = build_chunks()
    print(f"[2] 分片数: {len(chunks)}")

    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    file_count, total_split_pages = execute_split(chunks)

    print(f"\n[验证] 原始: {TOTAL_PAGES}页")
    print(f"[验证] 分片: {file_count}个文件, {total_split_pages}页")

    # 页面覆盖检查
    all_covered = set()
    for chunk in chunks:
        all_covered.update(range(chunk["start"], chunk["end"] + 1))
    all_pages = set(range(1, TOTAL_PAGES + 1))
    missing = sorted(all_pages - all_covered)
    if missing:
        print(f"[警告] 缺失页面: {missing}")
    else:
        print(f"[验证] 页面覆盖: 完整 ✓")

    if total_split_pages == TOTAL_PAGES:
        print(f"[验证] 页数守恒: ✓")
    else:
        print(f"[验证] 差异: {total_split_pages - TOTAL_PAGES}页")


if __name__ == "__main__":
    main()
