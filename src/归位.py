#!/usr/bin/env python3
"""
归位 v4.0 - 万物归其所
每个文件回到它该在的位置

功能:
  模式1 - 仅重命名: 按规范改名，文件留在原地
  模式2 - 智能归档: 改名 + 分类 → Documents 体系
  模式3 - 快速查阅: 只看内容/分类建议，不动文件
  模式4 - Inbox清空: 扫描 00_inbox，批量归档
  模式5 - 桌面清理: 扫描 Desktop 散落文件，批量归档
  模式6 - 批量重命名: 指定文件夹，批量规范化命名
全部本地运行，无需联网，不耗 token
"""

import os, sys, re, json, subprocess, shutil
from datetime import datetime
from pathlib import Path

# ======================== 配置 ========================
DOCS = os.path.expanduser("~/Documents")
TODAY = datetime.now().strftime("%Y-%m-%d")
TODAY_COMPACT = datetime.now().strftime("%Y%m%d")
TARGET_DIRS = {
    "thesis":         f"{DOCS}/01 项目 projects/博士论文 phd_thesis",
    "publication":    f"{DOCS}/01 项目 projects/发表出版 publications",
    "research":       f"{DOCS}/01 项目 projects/研究项目 research_projects",
    "cv":             f"{DOCS}/05 个人 personal/简历 cv",
    "visa":           f"{DOCS}/05 个人 personal/签证 visa",
    "personal_other": f"{DOCS}/05 个人 personal/其他 misc",
    "literature":     f"{DOCS}/03 资源 resources/文献 literature",
    "image":          f"{DOCS}/03 资源 resources/图片 images",
    "template":       f"{DOCS}/03 资源 resources/模板 templates",
    "reference":      f"{DOCS}/03 资源 resources/参考 references",
    "code":           f"{DOCS}/06 代码 code/代码项目 code_projects",
    "installer":      f"{DOCS}/07 应用 apps/工具 Installers",
    "course":         f"{DOCS}/04 归档 archives/旧课程 other_courses",
    "meeting":        f"{DOCS}/01 项目 projects/博士论文 phd_thesis/10 汇报 presentations",
    "area":           f"{DOCS}/02 领域 areas",
    "inbox":          f"{DOCS}/00 待处理 inbox",
}

# ======================== 内容分析引擎 ========================

def get_spotlight_metadata(filepath):
    """用 macOS Spotlight 获取文件的丰富元数据（已索引内容）"""
    try:
        result = subprocess.run(
            ["mdls", "-json", filepath],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get(os.path.basename(filepath), {}) or data.get("", {})
    except: pass
    return {}

def extract_text_content(filepath):
    """提取文件文本内容（本地版）"""
    ext = Path(filepath).suffix.lower()
    text = ""

    # 方案1: 先用 Spotlight 已索引的文本内容（最快，零开销）
    md = get_spotlight_metadata(filepath)
    content = md.get("kMDItemTextContent", "")
    if content and len(content) > 50:
        text = content

    # 方案2: Spotlight 没索引到，用 Python 直接读
    if not text or len(text) < 50:
        try:
            if ext == ".pdf":
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    text = "\n".join(p.page_text for p in pdf.pages[:5] if p.page_text)
            elif ext == ".docx":
                import docx
                doc = docx.Document(filepath)
                text = "\n".join(p.text for p in doc.paragraphs)
            elif ext in (".txt", ".md", ".tex", ".bib", ".csv"):
                with open(filepath, "r", errors="ignore") as f:
                    text = f.read(5000)
            elif ext in (".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".sh"):
                with open(filepath, "r", errors="ignore") as f:
                    text = f.read(2000)
        except: pass

    return text[:5000]  # 最多取前 5000 字符

def extract_image_info(filepath):
    """提取图片信息（本地，无API）"""
    ext = Path(filepath).suffix.lower()
    info = {"kind": "图片"}
    try:
        from PIL import Image
        img = Image.open(filepath)
        info["width"] = img.width
        info["height"] = img.height
        info["format"] = img.format
        try:
            r = subprocess.run(
                ["vnAnalyze", filepath],
                capture_output=True, text=True, timeout=10
            )
            if r.stdout:
                info["vision"] = r.stdout[:500]
        except: pass
    except: pass
    md = get_spotlight_metadata(filepath)
    info["md"] = md
    name = Path(filepath).stem.lower()
    if any(k in name for k in ["screenshot", "screen", "截图", "wechat", "微信"]):
        info["kind"] = "截图"
    return info

# ======================== 智能分类引擎 ========================

TOPIC_MAP = {
    "thesis": "thesis", "dissertation": "thesis", "毕业论文": "thesis",
    "博士论文": "thesis", "phd": "thesis", "literature review": "thesis",
    "文献综述": "thesis", "prisma": "thesis",
    "research": "research", "study": "research", "genai": "research",
    "biesta": "research", "实验": "research", "数据": "research",
    "qualitative": "research", "quantitative": "research",
    "cv": "cv", "resume": "cv", "curriculum vitae": "cv", "简历": "cv",
    "visa": "visa", "passport": "visa", "签证": "visa",
    "immigration": "visa", "护照": "visa",
    "journal": "literature", "article": "literature", "conference": "literature",
    "springer": "literature", "elsevier": "literature",
    "taylor": "literature", "francis": "literature",
    "doi": "literature", "参考文献": "literature",
    "assignment": "course", "course": "course", "lecture": "course",
    "作业": "course", "课程": "course", "edprofs": "course",
    "edcurric": "course", "edusw": "course",
    "meeting": "meeting", "会议": "meeting", "supervision": "meeting",
    "agenda": "meeting", "minutes": "meeting",
    "python": "code", "javascript": "code", "typescript": "code",
    "react": "code", "node": "code", "import ": "code",
    "def ": "code", "function": "code", "class ": "code",
    "install": "installer", "setup": "installer", ".dmg": "installer",
    ".pkg": "installer", ".app": "installer",
}

def classify_by_content(text, filename, ext):
    """基于文件内容 + 文件名 智能分类"""
    lowername = filename.lower()
    scores = {}
    for keyword, category in TOPIC_MAP.items():
        score = 0
        if keyword in lowername:
            score += 30
        if keyword.startswith(".") and keyword == ext.lower():
            score += 25
        if text and keyword in text.lower():
            count = text.lower().count(keyword)
            score += min(count, 15)
        if score > 0:
            scores[category] = scores.get(category, 0) + score
    if scores:
        best = max(scores, key=scores.get)
        return best if scores[best] >= 10 else "inbox"
    return "inbox"

def classify_file(filepath):
    """完整分类流程"""
    path = Path(filepath)
    filename = path.name
    ext = path.suffix.lower()
    lowername = filename.lower()

    keywords = {
        "thesis": "thesis", "论文": "thesis", "dissertation": "thesis",
        "cv": "cv", "resume": "cv", "简历": "cv",
        "visa": "visa", "签证": "visa", "passport": "visa",
        "meeting": "meeting", "会议": "meeting", "supervision": "meeting",
        "screenshot": "image", "截图": "image",
    }
    for kw, cat in keywords.items():
        if kw in lowername:
            return cat

    type_map = {
        ".tex": "thesis", ".bib": "literature",
        ".docx": "course", ".doc": "course",
        ".pptx": "template", ".ppt": "template",
        ".xlsx": "reference", ".xls": "reference", ".csv": "reference",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".gif": "image", ".svg": "image", ".webp": "image",
        ".mp3": "reference", ".wav": "reference",
        ".mp4": "reference", ".mov": "reference",
        ".zip": "inbox", ".tar": "inbox", ".gz": "inbox",
        ".dmg": "installer", ".pkg": "installer",
        ".py": "code", ".js": "code", ".ts": "code",
        ".html": "code", ".css": "code", ".json": "code",
        ".md": "area",
    }
    if ext in type_map:
        cat = type_map[ext]
        if ext != ".pdf":
            return cat

    text = extract_text_content(filepath)
    return classify_by_content(text, filename, ext)


# ======================== 重命名引擎 ========================

def clean_name(name):
    """清理文件名中的杂音"""
    patterns = [
        r'^Screenshot[^_]*_?', r'^LWScreenShot[^_]*_?', r'^wechat_[^_]*_?',
        r'^gen-[0-9]*_?', r'^微信图片_[^_]*_?', r'\(\d+\)',
        r'^[0-9]{8}_?', r'^[0-9]{4}-[0-9]{2}-[0-9]{2}_?',
    ]
    for p in patterns:
        name = re.sub(p, '', name)
    return name.strip(' _-')

def generate_new_name(filename, category, text=""):
    """根据分类和内容生成新文件名"""
    path = Path(filename)
    name = path.stem
    ext = path.suffix
    if category == "thesis":
        return f"{TODAY}_{clean_name(name)}{ext}"
    elif category == "cv":
        return f"CV_SuningLiu_{TODAY}{ext}"
    elif category == "visa":
        return f"签证_{clean_name(name)}_{TODAY}{ext}"
    elif category == "image":
        clean = clean_name(name)
        if not clean or clean == name:
            clean = "图片"
        return f"{TODAY}_{clean}{ext}"
    elif category == "meeting":
        return f"{TODAY}_会议_{clean_name(name)}{ext}"
    elif category == "course":
        return f"{TODAY}_{clean_name(name)}{ext}"
    elif category == "literature":
        return filename
    elif category == "template":
        return f"{TODAY}_模板_{clean_name(name)}{ext}"
    elif category == "installer":
        return filename
    elif category == "code":
        return filename
    else:
        return f"{TODAY}_{clean_name(name)}{ext}"


# ======================== 主界面 ========================

def print_header():
    print("╔═══════════════════════════════════════════════╗")
    print("║     归位 v4.0 · 万物归其所                  ║")
    print("║     100% 本地运行 · 无需联网 · 不耗 token   ║")
    print("╚═══════════════════════════════════════════════╝")

MODE_NAMES = {
    "1": "仅重命名",
    "2": "智能归档",
    "3": "快速查阅",
    "4": "Inbox清空",
    "5": "桌面清理",
    "6": "批量重命名",
}

def select_mode():
    """选择运行模式"""
    print()
    print("  ┌─ 归位 · 请选择模式 ──────────────────────┐")
    print("  │                                          │")
    print("  │  [1] 仅重命名 — 原地改名，不改位置        │")
    print("  │  [2] 智能归档 — 改名 + 归入 Documents     │")
    print("  │  [3] 快速查阅 — 只看内容，不动文件        │")
    print("  │  [4] Inbox清空 — 批量清理待处理文件夹     │")
    print("  │  [5] 桌面清理 — 批量清理桌面散落文件       │")
    print("  │  [6] 批量重命名 — 整个文件夹统一改名       │")
    print("  │                                          │")
    print("  └──────────────────────────────────────────┘")
    print()
    while True:
        choice = input("  请输入模式 (1-6): ").strip()
        if choice in MODE_NAMES:
            print(f"  📌 当前模式: {MODE_NAMES[choice]}\n")
            return choice
        print("  请输入 1-6")

def scan_directory(dirpath, recursive=False):
    """扫描目录，返回文件列表（排除隐藏文件）"""
    files = []
    try:
        if recursive:
            for root, dirs, fnames in os.walk(dirpath):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if not f.startswith('.'):
                        files.append(os.path.join(root, f))
        else:
            for f in os.listdir(dirpath):
                if f.startswith('.'):
                    continue
                full = os.path.join(dirpath, f)
                if os.path.isfile(full):
                    files.append(full)
    except Exception as e:
        print(f"  ⚠️  扫描失败: {e}")
    return sorted(files)

def handle_rename_only(filepath, newname):
    """模式1: 原地重命名"""
    parent = os.path.dirname(filepath)
    dest = os.path.join(parent, newname)
    if os.path.exists(dest):
        base = Path(dest).stem
        e = Path(dest).suffix
        i = 1
        while os.path.exists(os.path.join(parent, f"{base}_{i}{e}")):
            i += 1
        dest = os.path.join(parent, f"{base}_{i}{e}")
    os.rename(filepath, dest)
    print(f"   ✅ 已重命名为: {Path(dest).name}")

def handle_archive(filepath, newname, target):
    """模式2/4/5: 归档"""
    dest = os.path.join(target, newname)
    if os.path.exists(dest):
        base = Path(dest).stem
        e = Path(dest).suffix
        i = 1
        while os.path.exists(os.path.join(target, f"{base}_{i}{e}")):
            i += 1
        dest = os.path.join(target, f"{base}_{i}{e}")
    shutil.move(filepath, dest)
    print("   ✅ 已完成")

def analyze_file(filepath):
    """分析单个文件，返回 (category, info, text, newname)"""
    path = Path(filepath)
    filename = path.name
    ext = path.suffix.lower()
    info = {}
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        info = extract_image_info(filepath)
    category = classify_file(filepath)
    text = extract_text_content(filepath) if category != "image" else ""
    newname = generate_new_name(filename, category, text)
    return category, info, text, newname

def show_analysis(filepath, category, info, newname):
    """打印分析结果"""
    path = Path(filepath)
    print(f"\n📄 {path.name}")
    md = get_spotlight_metadata(filepath)
    if md.get("kMDItemAuthors"):
        print(f"   作者: {', '.join(md['kMDItemAuthors'][:2])}")
    if md.get("kMDItemTitle"):
        print(f"   标题: {md['kMDItemTitle']}")
    if md.get("kMDItemWhereFroms"):
        print(f"   来源: {md['kMDItemWhereFroms'][0][:80]}")
    if info.get("kind") == "截图":
        print(f"   类型: 截图")
    if info.get("width"):
        print(f"   尺寸: {info['width']}×{info['height']}px")
    print(f"   识别为: {category}")
    if newname != path.name:
        print(f"   建议名: {newname}")


def process_files(flist, mode):
    """处理文件列表（拖拽传入或交互输入）"""
    for fp in flist:
        if not os.path.exists(fp):
            print(f"\n⚠️  找不到: {fp}")
            continue

        fn = Path(fp).name

        # 文件夹处理
        if os.path.isdir(fp):
            if mode == "1":
                print(f"\n📂 {fn}")
                rec = input("  包含子文件夹？(y/N): ").strip().lower() == 'y'
                subfiles = scan_directory(fp, recursive=rec)
                if not subfiles:
                    print("  文件夹内没有文件")
                    continue
                changes = [(sf, analyze_file(sf)[3]) for sf in subfiles]
                changes = [(sf, nj) for sf, nj in changes if Path(sf).name != nj]
                if not changes:
                    print("  所有文件名已规范")
                    continue
                print(f"  将重命名 {len(changes)} 个文件")
                if input("  确认执行？(Y/n): ").strip().lower() != 'n':
                    for sf, nj in changes:
                        handle_rename_only(sf, nj)
                    print(f"  ✅ {len(changes)} 个文件已重命名")
                continue
            if mode == "3":
                print(f"\n📂 {fn}（快速查阅不处理文件夹）")
                continue
            cat = classify_file(fp)
            target = TARGET_DIRS.get(cat, TARGET_DIRS["inbox"])
            if not os.path.exists(target):
                target = TARGET_DIRS["inbox"]
            print(f"\n📂 {fn}   → {target}")
            if input("  (Y)移动 (S)跳过: ").strip().lower() != 's':
                shutil.move(fp, target)
                print("   ✅")
            continue

        # 文件分析
        cat, info, text, nn = analyze_file(fp)
        target = TARGET_DIRS.get(cat, TARGET_DIRS["inbox"])
        if not os.path.exists(target):
            target = TARGET_DIRS["inbox"]
        show_analysis(fp, cat, info, nn)

        # 模式3: 快速查阅
        if mode == "3":
            print(f"   建议路径: {target}")
            if text:
                print(f"\n   📖 {text[:300]}...\n")
            cmd = input("  (R)切归档处理 (N)切重命名 (Q)跳过: ").strip().lower()
            if cmd == 'r':
                print(f"   → {target}")
                sub = input("  (R)改名归档 (M)仅移动: ").strip().lower()
                if sub in ('r', 'm'):
                    handle_archive(fp, nn if sub == 'r' else fn, target)
            elif cmd == 'n':
                if input("  (R)重命名: ").strip().lower() == 'r':
                    handle_rename_only(fp, nn)
            continue

        # 模式2: 智能归档
        if mode == "2":
            print(f"   → {target}\n")
            cmd = input("  (R)改名归档 (M)仅移动 (S)跳过 (V)看内容 (1)切重命名: ").strip().lower()
            if cmd == '1':
                handle_rename_only(fp, nn)
                continue
            if cmd == 'v':
                print(f"\n   📖 {text[:300] if text else '无文本'}...\n")
                cmd = input("  (R)改名归档 (M)仅移动 (S)跳过: ").strip().lower()
            if cmd in ('r', 'm'):
                handle_archive(fp, nn if cmd == 'r' else fn, target)
            elif cmd == 's':
                print("   ⏭️")
            continue

        # 模式1: 仅重命名
        if mode == "1":
            print("   模式: 仅重命名（留在原位）\n")
            cmd = input("  (R)重命名 (S)跳过 (A)切归档处理: ").strip().lower()
            if cmd == 'a':
                print(f"   → {target}")
                sub = input("  (R)改名归档 (M)仅移动: ").strip().lower()
                if sub in ('r', 'm'):
                    handle_archive(fp, nn if sub == 'r' else fn, target)
            elif cmd == 'r':
                handle_rename_only(fp, nn)
            continue


def main():
    print_header()

    # === 从 .app 拖拽传入文件 ===
    if len(sys.argv) > 1:
        dropped = [f for f in sys.argv[1:] if os.path.exists(f)]
        if dropped:
            print(f"📥 收到 {len(dropped)} 个文件\n")
            mode = select_mode()

            # 模式4/5 在拖拽模式下不适用
            if mode in ("4", "5"):
                print("⚠️  该模式不支持拖拽操作，请双击 app 使用")
                input("\n按回车退出...")
                return
            if mode == "6":
                print("⚠️  批量重命名请拖拽文件夹，或双击 app 使用")
                input("\n按回车退出...")
                return

            process_files(dropped, mode)
            print("\n全部处理完毕！按回车键关闭")
            input()
            return

    # === 交互模式 ===
    mode = select_mode()

    # 模式4: Inbox清空
    if mode == "4":
        inbox = os.path.expanduser("~/Documents/00 待处理 inbox")
        flist = scan_directory(inbox)
        if not flist:
            print("📭 00 待处理 inbox 已经是空的！")
            input("\n按回车退出...")
            return
        print(f"📭 发现 {len(flist)} 个文件\n")
        for i, fp in enumerate(flist, 1):
            cat, info, text, nn = analyze_file(fp)
            target = TARGET_DIRS.get(cat, TARGET_DIRS["inbox"])
            if not os.path.exists(target):
                target = TARGET_DIRS["inbox"]
            show_analysis(fp, cat, info, nn)
            print(f"   → {target}\n")
            cmd = input(f"  [{i}/{len(flist)}] (R)改名归档 (M)仅移动 (S)跳过 (B)全部处理: ").strip().lower()
            if cmd == 'b':
                for j in range(i - 1, len(flist)):
                    cj, _, _, nj = analyze_file(flist[j])
                    tj = TARGET_DIRS.get(cj, TARGET_DIRS["inbox"])
                    if not os.path.exists(tj):
                        tj = TARGET_DIRS["inbox"]
                    handle_archive(flist[j], nj, tj)
                break
            elif cmd in ('r', 'm'):
                handle_archive(fp, nn if cmd == 'r' else Path(fp).name, target)
            elif cmd == 's':
                print("   ⏭️")
        input("\n处理完毕，按回车关闭...")
        return

    # 模式5: 桌面清理
    if mode == "5":
        desk = os.path.expanduser("~/Desktop")
        flist = scan_directory(desk)
        if not flist:
            print("🖥️ 桌面没有散落文件！")
            input("\n按回车退出...")
            return
        print(f"🖥️ 桌面有 {len(flist)} 个散落文件\n")
        for fp in flist:
            cat, info, text, nn = analyze_file(fp)
            target = TARGET_DIRS.get(cat, TARGET_DIRS["inbox"])
            if not os.path.exists(target):
                target = TARGET_DIRS["inbox"]
            show_analysis(fp, cat, info, nn)
            print(f"   → {target}\n")
            cmd = input("  (R)改名归档 (M)仅移动 (S)跳过 (Q)退出: ").strip().lower()
            if cmd == 'q':
                break
            elif cmd in ('r', 'm'):
                handle_archive(fp, nn if cmd == 'r' else Path(fp).name, target)
            else:
                print("   ⏭️")
        input("\n处理完毕，按回车关闭...")
        return

    # 模式6: 批量重命名
    if mode == "6":
        print("拖拽文件夹到下方，按回车：\n")
        raw = input().strip()
        folder = raw.strip("'\" \t")
        if not os.path.isdir(folder):
            print("⚠️  无效的文件夹路径")
            input("\n按回车退出...")
            return
        rec = input("  包含子文件夹？(y/N): ").strip().lower() == 'y'
        flist = scan_directory(folder, recursive=rec)
        if not flist:
            print("文件夹内没有文件")
            input("\n按回车退出...")
            return
        print(f"\n📂 {os.path.basename(folder)} 中共 {len(flist)} 个文件{'（含子文件夹）' if rec else ''}\n")
        changes = []
        for fp in flist:
            cat, _, _, nn = analyze_file(fp)
            fn = Path(fp).name
            if nn != fn:
                changes.append((fp, fn, nn))
        if not changes:
            print("所有文件名已符合规范，无需修改")
            input("\n按回车退出...")
            return
        print(f"将重命名 {len(changes)} 个文件：\n")
        for _, old, new in changes[:20]:
            print(f"  {old:<45}  →  {new}")
        if len(changes) > 20:
            print(f"  ... 还有 {len(changes) - 20} 个")
        print()
        if input("确认执行全部重命名？(Y/n): ").strip().lower() != 'n':
            for fp, _, nn in changes:
                handle_rename_only(fp, nn)
            print(f"\n✅ {len(changes)} 个文件已重命名")
        input("\n按回车关闭...")
        return

    # 模式1/2/3: 拖拽模式
    print("拖拽文件或文件夹到下方，按回车：")
    print("（可一次拖多个）\n")
    raw = input().strip()
    flist = []
    for part in raw.split():
        p = part.strip("'\" \t")
        if os.path.exists(p):
            flist.append(p)
    if not flist:
        print("⚠️  未识别到文件路径")
        input("\n按回车退出...")
        return

    process_files(flist, mode)

    print("\n═══════════════════════════════════════════════")
    print("全部处理完毕！按回车键关闭")
    input()


if __name__ == "__main__":
    main()
