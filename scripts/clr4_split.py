#!/usr/bin/env python3
"""
算法导论 第四版 (CLRS 4th Edition) - 小节级分片脚本 v3

优化：
  1. Problems 独立分片（每章末尾的 Problems + Chapter notes 单独提取）
  2. 修正跨章假重叠（跨章/跨Part边界精确切割，同章小节间保留1页重叠）
  3. 附录层级修正（A.x/B.x/C.x/D.x 从 L1 提升为 L2）
"""
import os
import re
import csv
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/168c0ea7-2393-4e07-9ee2-c522202d30ad_算法导论 第四版.pdf"
OUTPUT_ROOT = "/workspace/算法导论_第四版"
TOTAL_PAGES = 1676

# 辅助材料：(文件名, PDF起始页, PDF结束页)
AUXILIARY = [
    ("封面", 1, 3),
    ("Copyright", 4, 12),
    ("Preface", 13, 23),
    ("Part_I_Foundations_篇首页", 24, 24),
    ("Part_II_Sorting_and_Order_Statistics_篇首页", 223, 223),
    ("Part_III_Data_Structures_篇首页", 339, 339),
    ("Part_IV_Advanced_Design_and_Analysis_篇首页", 479, 479),
    ("Part_V_Advanced_Data_Structures_篇首页", 630, 630),
    ("Part_VI_Graph_Algorithms_篇首页", 715, 715),
    ("Part_VII_Selected_Topics_篇首页", 964, 964),
    ("Part_VIII_Appendix_篇首页", 1466, 1466),
    ("Bibliography", 1571, 1597),
    ("Index", 1598, TOTAL_PAGES),
]

# Part 目录映射：篇首页页码 -> Part目录名
PART_DIRS = {
    24: "Part_I_Foundations",
    223: "Part_II_Sorting_and_Order_Statistics",
    339: "Part_III_Data_Structures",
    479: "Part_IV_Advanced_Design_and_Analysis_Techniques",
    630: "Part_V_Advanced_Data_Structures",
    715: "Part_VI_Graph_Algorithms",
    964: "Part_VII_Selected_Topics",
    1466: "Part_VIII_Appendix__Mathematical_Background",
}

# 每章 Problems 起始页（通过 OCR + 视觉验证确定）
# 值为 Problems 标题页的 PDF 绝对页码（1-based）
PROBLEMS_PAGES = {
    1: 41, 2: 78, 3: 112, 4: 175, 5: 219,
    6: 251, 7: 276, 8: 301, 9: 332, 10: 363,
    11: 413, 12: 436, 13: 473, 14: 540, 15: 591,
    16: 624, 17: 654, 18: 680, 19: 710, 20: 757,
    21: 778, 22: 829, 23: 864, 24: 902, 25: 958,
    26: 1015, 27: 1056, 28: 1095, 29: 1128, 30: 1159,
    31: 1229, 32: 1283, 33: 1337, 34: 1415, 35: 1566,
}

# 每章标题页码（从书签提取，用于确定 Problems 结束页）
CHAPTER_START_PAGES = {}  # 将在 parse_bookmarks 中填充

# ==================== 工具函数 ====================

def sanitize(title):
    """清理标题为合法文件名"""
    name = re.sub(r'^★\s*', '', title)
    name = name.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('—', '-')
    name = re.sub(r'\s+', '_', name.strip())
    return name


def get_part_dir(page):
    """根据页码获取所属 Part 目录名"""
    result = ""
    for p in sorted(PART_DIRS.keys()):
        if p <= page:
            result = PART_DIRS[p]
        else:
            break
    return result


# ==================== 书签解析 ====================

def parse_bookmarks():
    """解析书签，返回结构化列表"""
    global CHAPTER_START_PAGES
    pdf_doc = pdfium.PdfDocument(INPUT_PDF)
    toc = list(pdf_doc.get_toc())

    bookmarks = []
    for entry in toc:
        title = entry.get_title()
        level = entry.level
        dest = entry.get_dest()
        page = dest.get_index() + 1 if dest else None
        bookmarks.append({"title": title, "page": page, "level": level})

        # 收集章标题页码
        if level == 1 and re.match(r'^\d+\s+', title):
            ch_num = int(re.match(r'^(\d+)', title).group(1))
            CHAPTER_START_PAGES[ch_num] = page

    return bookmarks


# ==================== 分片列表构建 ====================

def build_chunks(bookmarks):
    """构建完整分片列表"""
    chunks = []

    # --- 辅助材料 ---
    for name, start, end in AUXILIARY:
        chunks.append({
            "title": name, "start": start, "end": end,
            "dir": "00_辅助材料", "filename": f"{name}.pdf",
            "category": "辅助材料",
        })

    # --- 收集书签条目 ---
    entries = []
    for bm in bookmarks:
        title = bm["title"]
        page = bm["page"]
        level = bm["level"]

        # 附录子节提升为 L2
        if level == 1 and re.match(r'^(★\s*)?[A-D]\.\d+', title):
            eff_level = 2
        else:
            eff_level = level

        entries.append({
            "title": title, "page": page,
            "level": level, "eff_level": eff_level,
        })

    entries.sort(key=lambda x: x["page"])

    # --- 为每章构建 Problems 分片 ---
    for ch_num, prob_start in sorted(PROBLEMS_PAGES.items()):
        # 确定 Problems 结束页 = 下一章起始页 - 1
        if ch_num + 1 in CHAPTER_START_PAGES:
            prob_end = CHAPTER_START_PAGES[ch_num + 1] - 1
        elif ch_num == 35:
            prob_end = 1570  # Bibliography 前一页
        else:
            prob_end = TOTAL_PAGES

        prob_end = min(prob_end, TOTAL_PAGES)
        if prob_start > prob_end:
            continue

        # 确定 Problems 所属章节目录
        ch_title = _get_chapter_title(entries, ch_num)
        ch_dir = sanitize(ch_title) if ch_title else f"Ch{ch_num}"
        part_dir = get_part_dir(prob_start)

        chunks.append({
            "title": f"Ch{ch_num} Problems",
            "start": prob_start, "end": prob_end,
            "dir": os.path.join(part_dir, ch_dir),
            "filename": "Problems.pdf",
            "category": "Problems",
        })

    # --- 遍历书签条目，生成小节/章标题页/篇引言分片 ---
    for i, entry in enumerate(entries):
        title = entry["title"]
        page = entry["page"]
        eff = entry["eff_level"]
        part_dir = get_part_dir(page)

        # 计算结束页
        end_page = TOTAL_PAGES
        for j in range(i + 1, len(entries)):
            if entries[j]["eff_level"] <= eff:
                if eff == 2:
                    # L2 小节：检查是否跨章
                    next_eff = entries[j]["eff_level"]
                    if next_eff <= 1:
                        # 下一章/Part/篇引言：精确切割（不重叠）
                        end_page = entries[j]["page"] - 1
                    else:
                        # 同章下一小节：保留 1 页重叠
                        end_page = entries[j]["page"]
                else:
                    end_page = entries[j]["page"] - 1
                break

        # 如果该小节所属章节有 Problems，限制结束页不超过 Problems 起始页
        if eff == 2:
            ch_num = _get_chapter_num(entries, i)
            if ch_num and ch_num in PROBLEMS_PAGES:
                prob_start = PROBLEMS_PAGES[ch_num]
                if end_page >= prob_start:
                    # 保留 1 页重叠（节末练习 → Problems 过渡）
                    end_page = prob_start
                # 如果 end_page 已经 < prob_start，保持不变

        end_page = min(end_page, TOTAL_PAGES)
        if end_page < page:
            continue

        if eff == 2:
            ch_dir = _find_chapter_dir(entries, i)
            chunks.append({
                "title": title, "start": page, "end": end_page,
                "dir": os.path.join(part_dir, ch_dir) if ch_dir else part_dir,
                "filename": f"{sanitize(title)}.pdf",
                "category": "小节",
            })

        elif eff == 1:
            if title.strip() == "Introduction":
                chunks.append({
                    "title": title, "start": page, "end": end_page,
                    "dir": part_dir, "filename": "Introduction.pdf",
                    "category": "篇引言",
                })
            elif re.match(r'^\d+\s+', title):
                next_l2_page = _find_next_l2_page(entries, i)
                if next_l2_page and next_l2_page > page:
                    ch_dir = sanitize(title)
                    chunks.append({
                        "title": title, "start": page, "end": next_l2_page - 1,
                        "dir": os.path.join(part_dir, ch_dir),
                        "filename": f"{sanitize(title)}_标题页.pdf",
                        "category": "章标题页",
                    })
            elif re.match(r'^[A-D]\s+', title):
                next_l2_page = _find_next_l2_page(entries, i)
                if next_l2_page and next_l2_page > page:
                    ch_dir = f"Appendix_{sanitize(title)}"
                    chunks.append({
                        "title": title, "start": page, "end": next_l2_page - 1,
                        "dir": os.path.join(part_dir, ch_dir),
                        "filename": f"{sanitize(title)}.pdf",
                        "category": "附录标题页",
                    })

    return chunks


def _get_chapter_num(entries, idx):
    """为 L2 条目确定所属章号"""
    for j in range(idx - 1, -1, -1):
        e = entries[j]
        if e["eff_level"] == 1:
            m = re.match(r'^(\d+)\s+', e["title"])
            if m:
                return int(m.group(1))
        if e["eff_level"] == 0:
            break
    return None


def _get_chapter_title(entries, ch_num):
    """根据章号获取完整章标题（含章号，如 '2 Getting Started'）"""
    for e in entries:
        if e["eff_level"] == 1:
            m = re.match(r'^(\d+)\s+', e["title"])
            if m and int(m.group(1)) == ch_num:
                return e["title"]
    return ""


def _find_next_l2_page(entries, idx):
    """从 idx 之后找到下一个 L2 条目的页码"""
    for j in range(idx + 1, len(entries)):
        if entries[j]["eff_level"] == 2:
            return entries[j]["page"]
    return None


def _find_chapter_dir(entries, idx):
    """为 L2 条目找到所属章节目录名"""
    for j in range(idx - 1, -1, -1):
        e = entries[j]
        if e["eff_level"] == 1:
            t = e["title"]
            if re.match(r'^\d+\s+', t) or re.match(r'^[A-D]\s+', t):
                return sanitize(t)
        if e["eff_level"] == 0:
            break
    return ""


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
    print("算法导论 第四版 - 小节级分片 v3")
    print("优化: Problems独立分片 + 修正假重叠")
    print("=" * 60)

    print("\n[1] 解析书签...")
    bookmarks = parse_bookmarks()
    print(f"  书签总数: {len(bookmarks)}")
    print(f"  章标题: {len(CHAPTER_START_PAGES)} 个")
    print(f"  Problems: {len(PROBLEMS_PAGES)} 个")

    print("\n[2] 构建分片列表...")
    chunks = build_chunks(bookmarks)
    print(f"  分片条目: {len(chunks)}")

    print(f"\n[3] 执行分片 -> {OUTPUT_ROOT}")
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    file_count, total_pages, csv_rows = execute_split(chunks)

    # 统计
    print(f"\n{'='*60}")
    print(f"原始 PDF: {TOTAL_PAGES} 页")
    print(f"分片文件: {file_count} 个, 共 {total_pages} 页")
    if total_pages == TOTAL_PAGES:
        print(f"✅ 页数守恒")
    else:
        print(f"⚠ 页数差异: {total_pages - TOTAL_PAGES} (含重叠)")
    print(f"{'='*60}")

    # CSV
    csv_path = os.path.join(OUTPUT_ROOT, "分片清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["序号","类别","标题","起始页","结束页","页数","相对路径"])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\n分片清单: {csv_path}")


if __name__ == "__main__":
    main()
