# 安装依赖
# pip install ebooklib beautifulsoup4 edge-tts

import os
import re
import argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import edge_tts
import asyncio
import glob

# ====================== 【财经专用配置】 ======================
# 👉 只需要改这里 👈
BOOK_FOLDER = "/Users/yilin/Documents/Read/投资"
VOICE_FOLDER = "/Users/yilin/Documents/Read - Voice"
# TODO: change BOOK_NAME to the file that you want to generate voice for
BOOK_NAME = "不为人知的金融怪杰：11位市场交易奇才的故事"
EPUB_PATH = f"{BOOK_FOLDER}/{BOOK_NAME}.epub"
OUTPUT_FOLDER = f"{VOICE_FOLDER}/{BOOK_NAME}"
SCRIPT_FOLDER = f"{OUTPUT_FOLDER}/script"
'''
optional voice
zh-CN-XiaoxiaoNeural               Female    News, Novel            Warm
zh-CN-XiaoyiNeural                 Female    Cartoon, Novel         Lively
zh-CN-YunjianNeural                Male      Sports,  Novel         Passion
zh-CN-YunxiNeural                  Male      Novel                  Lively, Sunshine
zh-CN-YunxiaNeural                 Male      Cartoon, Novel         Cute
zh-CN-YunyangNeural                Male      News                   Professional, Reliable
zh-CN-liaoning-XiaobeiNeural       Female    Dialect                Humorous
zh-CN-shaanxi-XiaoniNeural         Female    Dialect                Bright
'''
VOICE = "zh-CN-YunyangNeural"  # 稳重男声（财经首选）
# VOICE = "en-GB-SoniaNeural"
# VOICE = "zh-CN-YunxiaNeural"  # 干练女声

# 财经语速：稍慢、清晰、专业
RATE = "-15%"
PITCH = "+0%"

# 前言/序言关键词，匹配的章节将被跳过以生成更自然的收听体验
PREFACE_KEYWORDS = [
    "preface", "前言", "序言", "foreword", "introduction",
    "致谢", "acknowledgment", "acknowledgement", "版权", "copyright",
]
# ==============================================================

# 创建输出文件夹
if not os.path.exists(OUTPUT_FOLDER):
    os.mkdir(OUTPUT_FOLDER)


def clean_text(text):
    # 清理多余空行、空格，适合朗读
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def sanitize_for_filename(s, max_len=60):
    """Make string safe for use in filenames."""
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return (s[:max_len] if s else "chapter") or "chapter"


def _extract_first_heading(soup):
    """Extract first h1 or h2 for preface detection."""
    for tag in ["h1", "h2", "h3"]:
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True).lower()
    return ""


def _is_preface(title):
    """Check if chapter title matches preface keywords."""
    if not title:
        return False
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in PREFACE_KEYWORDS)


def get_chapters_from_epub(epub_path):
    """
    Extract chapters in spine order.
    Returns list of (title, text, is_preface) tuples.
    """
    book = epub.read_epub(epub_path)
    chapters = []

    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(strip=False)
        text = clean_text(text)
        if len(text) <= 200:  # 过滤太短的无效页面
            continue
        heading = _extract_first_heading(soup)
        is_preface = _is_preface(heading)
        title = heading or f"Chapter {len(chapters) + 1}"
        chapters.append((title, text, is_preface))
    return chapters


def run_extract():
    """Extract text from epub to script folder, skipping preface."""
    if not os.path.exists(EPUB_PATH):
        print(f"❌ EPUB 文件不存在：{EPUB_PATH}")
        return
    os.makedirs(SCRIPT_FOLDER, exist_ok=True)
    print("正在读取 EPUB...")
    chapters = get_chapters_from_epub(EPUB_PATH)
    manifest_lines = []
    idx = 0
    for title, text, is_preface in chapters:
        if is_preface:
            manifest_lines.append(f"(skipped) {title} [preface]")
            continue
        idx += 1
        safe_title = sanitize_for_filename(title)
        filename = f"chapter_{idx:02d}_{safe_title}.txt"
        filepath = os.path.join(SCRIPT_FOLDER, filename)
        content = f"# {title}\n\n{text}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        manifest_lines.append(f"{idx:02d} - {title}")
        print(f"✅ 已导出：{filename}")
    manifest_path = os.path.join(SCRIPT_FOLDER, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines))
    print(f"\n📖 共导出 {idx} 个章节（已跳过前言）")
    print(f"📁 文本已保存至：{SCRIPT_FOLDER}")
    print("   请手动检查编辑后，运行 generate 生成音频")


def get_script_chapters():
    """Get (idx, title, text) for each chapter .txt in script folder, sorted."""
    if not os.path.exists(SCRIPT_FOLDER):
        return []
    files = sorted(glob.glob(os.path.join(SCRIPT_FOLDER, "chapter_*.txt")))
    result = []
    for fp in files:
        basename = os.path.basename(fp)
        # chapter_02.txt or chapter_02_Title_Here.txt
        match = re.match(r"chapter_(\d+)(?:_(.+))?\.txt$", basename)
        if not match:
            continue
        idx = int(match.group(1))
        title_part = match.group(2) or ""
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip optional # title header line for SSML
        lines = content.strip().split("\n")
        if lines and lines[0].startswith("# "):
            text = "\n".join(lines[1:]).strip()
        else:
            text = content.strip()
        result.append((idx, title_part, text))
    return sorted(result, key=lambda x: x[0])


AUDIO_FOLDER = f"{OUTPUT_FOLDER}/audio"


async def text_to_mp3(text, chapter_idx, total, title_suffix=""):
    safe_title = sanitize_for_filename(title_suffix) if title_suffix else ""
    name_part = f"_{safe_title}" if safe_title else "_财经有声书"
    filename = f"{chapter_idx:02d}_{name_part}.mp3"
    os.makedirs(AUDIO_FOLDER, exist_ok=True)
    filepath = os.path.join(AUDIO_FOLDER, filename)

    # SSML: voice + prosody only, script text as-is (no intro/outro)
    ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
<voice name="{VOICE}">
<prosody rate="{RATE}" pitch="{PITCH}" volume="medium">
{text}
</prosody>
</voice>
</speak>'''

    communicate = edge_tts.Communicate(ssml, voice=VOICE)
    await communicate.save(filepath)
    print(f"✅ 已生成：{filename}")


async def run_generate_all():
    """Generate audio for all chapters in script folder."""
    chapters = get_script_chapters()
    if not chapters:
        print("❌ script 文件夹为空或不存在，请先运行：python epub_to_mp3.py extract")
        return
    total = len(chapters)
    print(f"📖 共 {total} 个章节待生成\n")
    for idx, title_part, text in chapters:
        await text_to_mp3(text, idx, total, title_part)
    print(f"\n🎉 全部完成！音频在：{AUDIO_FOLDER}")


async def run_generate_chapter(chapter_num):
    """Generate audio for a single chapter."""
    chapters = get_script_chapters()
    if not chapters:
        print("❌ script 文件夹为空或不存在，请先运行：python epub_to_mp3.py extract")
        return
    match = [(i, t, x) for i, t, x in chapters if i == chapter_num]
    if not match:
        valid = [i for i, _, _ in chapters]
        print(f"❌ 未找到章节 {chapter_num}，可用章节：{valid}")
        return
    idx, title_part, text = match[0]
    total = len(chapters)
    await text_to_mp3(text, idx, total, title_part)
    print(f"\n🎉 已生成第 {idx} 章")


def main():
    parser = argparse.ArgumentParser(description="epub 转有声书")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("extract", help="从 epub 提取文本到 script 文件夹，跳过前言")

    gen = subparsers.add_parser("generate", help="从 script 文件夹生成音频")
    gen.add_argument("--all", action="store_true", help="生成所有章节")
    gen.add_argument("--chapter", type=int, metavar="N", help="仅生成第 N 章")

    args = parser.parse_args()

    if args.command == "extract":
        run_extract()
    elif args.command == "generate":
        if args.all:
            asyncio.run(run_generate_all())
        elif args.chapter is not None:
            asyncio.run(run_generate_chapter(args.chapter))
        else:
            parser.error("generate 需要 --all 或 --chapter N")


if __name__ == "__main__":
    main()
