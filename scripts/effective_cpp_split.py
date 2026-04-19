#!/usr/bin/env python3
"""
Effective C++ 中文版 - 条款级分片脚本

纯扫描版 PDF（328页），无书签无文本层。
通过 Read 工具逐页扫描确定条款起始页，硬编码到脚本中。

特点：
  - 按条款（Item）粒度拆分，共 55 个条款
  - 条款归入对应章节文件夹
  - 零填充编号（条款01, 条款02, ...）
  - 同章条款间 1 页重叠
"""
import os
import re
import csv
import pypdfium2 as pdfium
from pypdf import PdfReader

# ==================== 配置 ====================

INPUT_PDF = "/workspace/.uploads/77a00399-bbe8-483c-8764-00c749c573f5_(已瘦身)《Effective C++ 中文版》.pdf"
OUTPUT_ROOT = "/workspace/Effective_Cpp_中文版"
TOTAL_PAGES = 328

# 辅助材料：(文件名, PDF起始页, PDF结束页)
AUXILIARY = [
    ("封面", 1, 4),
    ("版权页", 5, 9),
    ("扉页", 10, 10),
    ("术语对照表", 11, 19),
    ("目录", 20, 30),
    ("导读", 31, 41),
    ("附录B_新旧版条款对照", 310, 319),
    ("索引", 320, 328),
]

# 条款起始页（硬编码，来自 Read 工具逐页扫描 + 页眉校验）
# PDF页码 = 书页码 + 31
ITEM_PAGES = {
    1: 42, 2: 44, 3: 48, 4: 57, 5: 65, 6: 68, 7: 71, 8: 76, 9: 79,
    10: 84, 11: 85, 12: 89, 13: 94, 14: 97, 15: 100, 16: 104, 17: 108, 18: 110,
    19: 115, 20: 117, 21: 124, 22: 126, 23: 130, 24: 134, 25: 137, 26: 144, 27: 147,
    28: 154, 29: 158, 30: 165, 31: 171, 32: 184, 33: 187, 34: 194, 35: 204,
    36: 209, 37: 214, 38: 215, 39: 218, 40: 223, 41: 230, 42: 234, 43: 238,
    44: 243, 45: 249, 46: 253, 47: 257, 48: 264, 49: 271, 50: 278, 51: 283,
    52: 288, 53: 293, 54: 294, 55: 300,
}

# 条款标题
ITEM_TITLES = {
    1: "视C++为一个语言联邦",
    2: "尽量以const_enum_inline替换#define",
    3: "尽可能使用const",
    4: "确定对象被使用前已先被初始化",
    5: "了解C++默默编写并调用哪些函数",
    6: "若不想使用编译器自动生成的函数就该明确拒绝",
    7: "为多态基类声明virtual析构函数",
    8: "别让异常逃离析构函数",
    9: "绝不在构造和析构过程中调用virtual函数",
    10: "令operator=返回一个reference_to_this",
    11: "在operator=中处理自我赋值",
    12: "复制对象时勿忘其每一个成分",
    13: "以对象管理资源",
    14: "在资源管理类中小心copying行为",
    15: "在资源管理类中提供对原始资源的访问",
    16: "成对使用new和delete时要采取相同形式",
    17: "以独立语句将newed对象置入智能指针",
    18: "让接口容易被正确使用不易被误用",
    19: "设计class犹如设计type",
    20: "宁以pass-by-reference-to-const替换pass-by-value",
    21: "必须返回对象时别妄想返回其reference",
    22: "将成员变量声明为private",
    23: "宁以non-member_non-friend替换member函数",
    24: "若所有参数皆需类型转换请为此采用non-member函数",
    25: "考虑写出一个不抛异常的swap函数",
    26: "尽可能延后变量定义式的出现时间",
    27: "尽量少做转型动作",
    28: "避免返回handles指向对象内部成分",
    29: "为异常安全而努力是值得的",
    30: "透彻了解inlining的里里外外",
    31: "将文件间的编译依存关系降至最低",
    32: "确定你的public继承塑模出is-a关系",
    33: "避免遮掩继承而来的名称",
    34: "区分接口继承和实现继承",
    35: "考虑virtual函数以外的其他选择",
    36: "绝不重新定义继承而来的non-virtual函数",
    37: "绝不重新定义继承而来的缺省参数值",
    38: "通过复合塑模出has-a或根据某物实现出",
    39: "明智而审慎地使用private继承",
    40: "明智而审慎地使用多重继承",
    41: "了解隐式接口和编译期多态",
    42: "了解typename的双重意义",
    43: "学习处理模板化基类内的名称",
    44: "将与参数无关的代码抽离templates",
    45: "运用成员函数模板接受所有兼容类型",
    46: "需要类型转换时请为模板定义非成员函数",
    47: "请使用traits_classes表现类型信息",
    48: "认识template元编程",
    49: "了解new-handler的行为",
    50: "了解new和delete的合理替换时机",
    51: "编写new和delete时需固守常规",
    52: "写了placement_new也要写placement_delete",
    53: "不要轻忽编译器的警告",
    54: "让自己熟悉包括TR1在内的标准程序库",
    55: "让自己熟悉Boost",
}

# 章节映射：条款编号 → (章节目录名, 章节标题)
# Effective C++ 第三版共 8 章
CHAPTERS = [
    (1, 4, "01_让自己习惯C++", "让自己习惯C++"),
    (5, 12, "02_构造_析构_赋值运算", "构造/析构/赋值运算"),
    (13, 17, "03_资源管理", "资源管理"),
    (18, 22, "04_设计与声明", "设计与声明"),
    (23, 30, "05_实现", "实现"),
    (31, 40, "06_继承与面向对象设计", "继承与面向对象设计"),
    (41, 48, "07_模板与泛型编程", "模板与泛型编程"),
    (49, 55, "08_定制new和delete", "定制new和delete"),
]

# ==================== 工具函数 ====================

def sanitize(title):
    """清理标题为合法文件名"""
    name = title.replace(':', '_').replace('?', '').replace('/', '_')
    name = name.replace('\\', '_').replace('"', '').replace('—', '-')
    name = re.sub(r'\s+', '_', name.strip())
    return name


def find_chapter(item_num):
    """根据条款编号确定所属章节"""
    for start, end, dir_name, title in CHAPTERS:
        if start <= item_num <= end:
            return dir_name, title
    return "00_辅助材料", "辅助材料"


# ==================== 分片列表构建 ====================

def build_chunks():
    """构建完整分片列表"""
    chunks = []

    # --- 辅助材料 ---
    for name, start, end in AUXILIARY:
        chunks.append({
            "title": name, "start": start, "end": end,
            "dir": "00_辅助材料", "filename": f"{sanitize(name)}.pdf",
            "category": "辅助材料",
        })

    # --- 条款 ---
    sorted_items = sorted(ITEM_PAGES.keys())
    for i, item_num in enumerate(sorted_items):
        page = ITEM_PAGES[item_num]
        title = ITEM_TITLES.get(item_num, f"条款{item_num:02d}")
        ch_dir, ch_title = find_chapter(item_num)

        # 结束页：下一个条款起始页 - 1（同章内 1 页重叠）
        if i + 1 < len(sorted_items):
            next_page = ITEM_PAGES[sorted_items[i + 1]]
            next_ch_dir, _ = find_chapter(sorted_items[i + 1])
            if next_ch_dir == ch_dir:
                # 同章：1 页重叠
                end_page = next_page
            else:
                # 跨章：精确切割
                end_page = next_page - 1
        else:
            # 最后一个条款：到附录前
            end_page = 309  # 附录B从p310开始

        end_page = min(end_page, TOTAL_PAGES)
        if end_page < page:
            continue

        chunks.append({
            "title": f"条款{item_num:02d}_{title}",
            "start": page, "end": end_page,
            "dir": ch_dir,
            "filename": f"条款{item_num:02d}_{sanitize(title)}.pdf",
            "category": "条款",
        })

    return chunks


# ==================== 分片执行 ====================

def execute_split(chunks):
    """执行 PDF 分片（使用 pypdfium2，兼容性更好）"""
    src_doc = pdfium.PdfDocument(INPUT_PDF)
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

        # 用 pypdfium2 导入页面（生成 PDF-1.7，兼容 Acrobat）
        dest_doc = pdfium.PdfDocument.new()
        dest_doc.import_pages(src_doc, list(range(start - 1, end)))

        out_path = os.path.join(out_dir, chunk["filename"])
        dest_doc.save(out_path)

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
    print("Effective C++ 中文版 - 条款级分片")
    print("=" * 60)

    print(f"\n[1] PDF信息: {TOTAL_PAGES} 页, {len(ITEM_PAGES)} 个条款")

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
