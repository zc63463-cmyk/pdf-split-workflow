#!/usr/bin/env python3
"""
深入理解计算机系统 第3版 (CSAPP 3rd Edition) - 小节级分片脚本

基于书签驱动分片，按小节粒度拆分。
特点：
  - 第1章小节(1.1-1.10)为 L1，需层级修正
  - 第2-12章小节为 L2，直接分片
  - 每章末尾的"家庭作业"和"练习题答案"已有独立书签
  - 同章小节间 1 页重叠，跨章精确切割
"""
import os
import re
import csv
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/ed48836b-6c26-44c2-8bd9-d241bf02a199_深入理解计算机系统（原书第3版）扫描版可编辑 (Randal E.Bryant David OHallaron) .pdf"
OUTPUT_ROOT = "/workspace/深入理解计算机系统_第3版"
TOTAL_PAGES = 775

# 辅助材料：(文件名, PDF起始页, PDF结束页)
AUXILIARY = [
    ("封面", 1, 4),
    ("出版者的话", 5, 6),
    ("中文版序一", 7, 9),
    ("中文版序二", 10, 11),
    ("译者序", 12, 12),
    ("前言", 13, 27),
    ("关于作者", 28, 29),
    ("目录", 30, 36),
    ("附录A_错误处理", 764, 767),
    ("参考文献", 768, 775),
    ("Part_I_程序结构和执行", 57, 57),
    ("Part_II_在系统上运行程序", 499, 499),
    ("Part_III_程序间的交流和通信", 656, 656),
]

# Part 目录映射：Part标题页码 -> Part目录名
PART_DIRS = {
    57: "Part_I_程序结构和执行",
    499: "Part_II_在系统上运行程序",
    656: "Part_III_程序间的交流和通信",
}

# ==================== 工具函数 ====================

def sanitize(title):
    """清理标题为合法文件名"""
    name = title.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('—', '-')
    name = name.replace('+', '_')
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


def is_section_title(title):
    """判断标题是否为小节标题（如 1.1, 2.3）"""
    return bool(re.match(r'^\d+\.\d+', title))


def is_chapter_title(title):
    """判断标题是否为章标题（如 第2章, 第一章）"""
    return bool(re.match(r'^第[一二三四五六七八九十\d]+章', title))


# ==================== 书签解析 ====================

def parse_bookmarks():
    """解析书签，返回结构化列表"""
    pdf_doc = pdfium.PdfDocument(INPUT_PDF)
    toc = list(pdf_doc.get_toc())

    bookmarks = []
    for entry in toc:
        title = entry.get_title()
        level = entry.level
        dest = entry.get_dest()
        page = dest.get_index() + 1 if dest else None
        bookmarks.append({"title": title, "page": page, "level": level})

    # 层级修正：第1章小节(1.x)为 L1，提升为有效 L2
    # 第1章的"参考答案、练习题答案"也为 L1，同样提升
    for bm in bookmarks:
        if bm["level"] == 1 and (is_section_title(bm["title"]) or "参考答案" in bm["title"] or "练习题答案" in bm["title"]):
            bm["eff_level"] = 2
        else:
            bm["eff_level"] = bm["level"]

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
        entries.append({
            "title": bm["title"], "page": bm["page"],
            "level": bm["level"], "eff_level": bm["eff_level"],
        })

    entries.sort(key=lambda x: x["page"])

    # --- 遍历书签条目，生成分片 ---
    for i, entry in enumerate(entries):
        title = entry["title"]
        page = entry["page"]
        eff = entry["eff_level"]
        level = entry["level"]

        # 计算结束页
        end_page = TOTAL_PAGES
        for j in range(i + 1, len(entries)):
            if entries[j]["eff_level"] <= eff:
                if eff == 2:
                    next_eff = entries[j]["eff_level"]
                    if next_eff <= 1:
                        end_page = entries[j]["page"] - 1  # 跨章精确切割
                    else:
                        end_page = entries[j]["page"]  # 同章保留重叠
                else:
                    end_page = entries[j]["page"] - 1
                break

        end_page = min(end_page, TOTAL_PAGES)
        if end_page < page:
            continue

        if eff == 2:
            # === 小节：独立分片 ===
            ch_dir = _find_chapter_dir(entries, i)
            part_dir = get_part_dir(page)

            # 第1章小节无 Part，直接放在章目录下
            if not part_dir:
                part_dir = ""  # 会在 ch_dir 中处理

            dir_path = os.path.join(part_dir, ch_dir) if part_dir and ch_dir else (ch_dir or part_dir)
            filename = f"{sanitize(title)}.pdf"

            # 判断类别
            if "练习题答案" in title:
                category = "练习题答案"
            elif "家庭作业" in title:
                category = "家庭作业"
            elif "参考文献说明" in title:
                category = "参考文献说明"
            else:
                category = "小节"

            chunks.append({
                "title": title, "start": page, "end": end_page,
                "dir": dir_path, "filename": filename,
                "category": category,
            })

        elif eff == 1 and is_chapter_title(title):
            # === 章标题：仅当与下一小节不同页时独立分片 ===
            next_l2_page = _find_next_l2_page(entries, i)
            if next_l2_page and next_l2_page > page:
                ch_dir = sanitize(title)
                part_dir = get_part_dir(page)
                dir_path = os.path.join(part_dir, ch_dir) if part_dir else ch_dir
                chunks.append({
                    "title": title, "start": page, "end": next_l2_page - 1,
                    "dir": dir_path,
                    "filename": f"{sanitize(title)}_标题页.pdf",
                    "category": "章标题页",
                })

    return chunks


def _find_next_l2_page(entries, idx):
    for j in range(idx + 1, len(entries)):
        if entries[j]["eff_level"] == 2:
            return entries[j]["page"]
    return None


def _find_chapter_dir(entries, idx):
    """为 L2 条目找到所属章节目录名"""
    for j in range(idx - 1, -1, -1):
        e = entries[j]
        if e["eff_level"] == 1 and is_chapter_title(e["title"]):
            return sanitize(e["title"])
        if e["eff_level"] == 0:
            break
    # 第1章无独立章标题书签，根据小节编号或相邻条目推断
    entry = entries[idx]
    if re.match(r'^(1\.\d+)', entry["title"]):
        return "第1章_计算机系统漫游"
    # 练习题答案等：检查相邻条目是否属于第1章
    for j in range(idx - 1, -1, -1):
        if re.match(r'^(1\.\d+)', entries[j]["title"]):
            return "第1章_计算机系统漫游"
        if entries[j]["eff_level"] == 0:
            break
    return ""


# ==================== 分片执行 ====================

def execute_split(chunks):
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
    print("深入理解计算机系统 第3版 - 小节级分片")
    print("=" * 60)

    print("\n[1] 解析书签...")
    bookmarks = parse_bookmarks()
    print(f"  书签总数: {len(bookmarks)}")

    print("\n[2] 构建分片列表...")
    chunks = build_chunks(bookmarks)
    print(f"  分片条目: {len(chunks)}")

    print(f"\n[3] 执行分片 -> {OUTPUT_ROOT}")
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    file_count, total_pages, csv_rows = execute_split(chunks)

    print(f"\n{'='*60}")
    print(f"原始 PDF: {TOTAL_PAGES} 页")
    print(f"分片文件: {file_count} 个, 共 {total_pages} 页")
    if total_pages == TOTAL_PAGES:
        print(f"✅ 页数守恒")
    else:
        print(f"⚠ 页数差异: {total_pages - TOTAL_PAGES} (含重叠)")
    print(f"{'='*60}")

    csv_path = os.path.join(OUTPUT_ROOT, "分片清单.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["序号","类别","标题","起始页","结束页","页数","相对路径"])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\n分片清单: {csv_path}")


if __name__ == "__main__":
    main()
