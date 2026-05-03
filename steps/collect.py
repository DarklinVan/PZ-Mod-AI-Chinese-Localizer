import os
import re
import shutil
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import ORIGINAL_DIR, TEMP_DIR, TRANSLATE_EN, FILE_BLACKLIST


def _find_mod_info(workshop_path):
    for root, dirs, files in os.walk(workshop_path):
        for f in files:
            if f.lower() == 'mod.info':
                return os.path.join(root, f)
    return None


def _parse_mod_name(mod_info_path):
    with open(mod_info_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = re.match(r'^name=(.+)', line.strip())
            if m:
                raw = m.group(1).strip()
                return re.sub(r'[<>:"/\\|?*]', '_', raw)
    return None


def _find_en_files(workshop_path):
    results = []
    target = str(TRANSLATE_EN).lower()
    for root, dirs, files in os.walk(workshop_path):
        if root.lower().endswith(target):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.txt', '.json'):
                    results.append(os.path.join(root, f))
    return results


def run():
    if not ORIGINAL_DIR.is_dir():
        print(f'原始目录不存在: {ORIGINAL_DIR}')
        return

    total = 0
    for wid in sorted(os.listdir(ORIGINAL_DIR)):
        wspath = os.path.join(ORIGINAL_DIR, wid)
        if not os.path.isdir(wspath):
            continue

        mod_info = _find_mod_info(wspath)
        if not mod_info:
            print(f'[{wid}] 未找到 mod.info，跳过')
            continue

        mod_name = _parse_mod_name(mod_info)
        if not mod_name:
            print(f'[{wid}] mod.info 中未找到 name，跳过')
            continue

        en_files = _find_en_files(wspath)
        if not en_files:
            print(f'[{wid}] {mod_name}  — 无 Translate/EN 文件')
            continue

        dest = os.path.join(TEMP_DIR, wid, mod_name, TRANSLATE_EN)
        os.makedirs(dest, exist_ok=True)

        for src in en_files:
            fn = os.path.basename(src)
            if fn.lower() in FILE_BLACKLIST:
                print(f'  [跳过] {fn}')
                continue
            shutil.copy2(src, os.path.join(dest, fn))
            total += 1

        print(f'[{wid}] {mod_name}  — {len(en_files)} 个文件')

    print(f'\n完成! 共复制 {total} 个文件')
