import os
import re
import shutil
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import ORIGINAL_DIR, TEMP_DIR, TRANSLATE_EN, FILE_BLACKLIST
from logger import logger


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
    logger.info('步骤1: 收集EN翻译文件 — 开始')
    logger.debug(f'ORIGINAL_DIR={ORIGINAL_DIR}, TEMP_DIR={TEMP_DIR}, TRANSLATE_EN={TRANSLATE_EN}')

    if not ORIGINAL_DIR.is_dir():
        logger.error(f'原始目录不存在: {ORIGINAL_DIR}')
        print(f'原始目录不存在: {ORIGINAL_DIR}')
        return

    workshop_dirs = sorted(os.listdir(ORIGINAL_DIR))
    logger.debug(f'在 original 中发现 {len(workshop_dirs)} 个目录')
    total = 0
    for wid in workshop_dirs:
        wspath = os.path.join(ORIGINAL_DIR, wid)
        if not os.path.isdir(wspath):
            logger.debug(f'[{wid}] 不是目录，跳过')
            continue

        mod_info = _find_mod_info(wspath)
        if not mod_info:
            logger.warn(f'[{wid}] 未找到 mod.info')
            print(f'[{wid}] 未找到 mod.info，跳过')
            continue
        logger.debug(f'[{wid}] mod_info_path={mod_info}')

        mod_name = _parse_mod_name(mod_info)
        if not mod_name:
            logger.warn(f'[{wid}] mod.info 中未找到 name')
            print(f'[{wid}] mod.info 中未找到 name，跳过')
            continue
        logger.debug(f'[{wid}] mod_name={mod_name!r}')

        en_files = _find_en_files(wspath)
        if not en_files:
            logger.debug(f'[{wid}] {mod_name}  — 无 Translate/EN 文件')
            print(f'[{wid}] {mod_name}  — 无 Translate/EN 文件')
            continue
        logger.debug(f'[{wid}] {mod_name} — 发现 {len(en_files)} 个 EN 文件: {[os.path.basename(f) for f in en_files]}')

        dest = os.path.join(TEMP_DIR, wid, mod_name, TRANSLATE_EN)
        os.makedirs(dest, exist_ok=True)
        logger.debug(f'[{wid}] 目标目录={dest}')

        copied = 0
        for src in en_files:
            fn = os.path.basename(src)
            if fn.lower() in FILE_BLACKLIST:
                logger.debug(f'[跳过] {fn}')
                print(f'  [跳过] {fn}')
                continue
            dest_path = os.path.join(dest, fn)
            shutil.copy2(src, dest_path)
            copied += 1
            total += 1
            logger.debug(f'[复制] {fn} -> {dest_path}')

        logger.info(f'[{wid}] {mod_name}  — 收集 {copied} 个文件')
        print(f'[{wid}] {mod_name}  — {copied} 个文件')

    logger.info(f'步骤1完成: 共复制 {total} 个文件')
    print(f'\n完成! 共复制 {total} 个文件')
