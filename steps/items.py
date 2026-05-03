import json
import os
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ORIGINAL_DIR, ONHOLD_DIR
from logger import logger

ITEM_BLOCK_RE = re.compile(
    r'^\s*item\s+(\S+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
    re.MULTILINE
)
DISPLAYNAME_RE = re.compile(r'DisplayName\s*=\s*(.+?),?\s*$', re.MULTILINE)
MODULE_RE = re.compile(r'^\s*module\s+(\S+)\s*\{', re.MULTILINE)


def _extract(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    logger.debug(f'_extract: 读取 {filepath.name} ({len(text)} 字符)')
    mod_m = MODULE_RE.search(text)
    module_name = mod_m.group(1) if mod_m else ''
    logger.debug(f'_extract: module_name={module_name!r}')

    items = {}
    for m in ITEM_BLOCK_RE.finditer(text):
        name = m.group(1)
        block = m.group(2)
        dn = DISPLAYNAME_RE.search(block)
        if dn:
            val = dn.group(1).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            full_id = f'{module_name}.{name}'
            items[full_id] = val
            logger.debug(f'_extract: 找到物品 {full_id} = {val!r}')
    return items


def run():
    logger.info('步骤3: 提取物品DisplayName — 开始')
    all_items = {}

    for wid in sorted(os.listdir(ORIGINAL_DIR)):
        wspath = ORIGINAL_DIR / wid
        if not wspath.is_dir():
            continue
        logger.debug(f'[{wid}] 扫描中...')
        mod_script_files = 0

        for root, dirs, files in os.walk(wspath):
            rp = Path(root)
            parts_lower = [p.lower() for p in rp.parts]
            if 'scripts' not in parts_lower:
                continue
            rel = [p.lower() for p in rp.relative_to(wspath).parts]
            try:
                si = rel.index('scripts')
            except ValueError:
                continue
            if si == 0 or rel[si - 1] != 'media':
                continue

            logger.debug(f'[{wid}] 进入 Scripts 目录: {rp}')
            for fn in files:
                if not fn.lower().endswith('.txt'):
                    continue
                filepath = rp / fn
                items = _extract(filepath)
                if items:
                    all_items.update(items)
                    mod_script_files += 1
                    logger.debug(f'[{wid}] {fn}: 提取 {len(items)} 个物品')

        if mod_script_files == 0:
            logger.debug(f'[{wid}] Scripts 下无物品文件')
        else:
            logger.debug(f'[{wid}] 共扫描 {mod_script_files} 个物品文件')

    if not all_items:
        logger.warn('未找到任何物品')
        print('未找到任何物品')
        return

    logger.info(f'共提取 {len(all_items)} 个物品')
    print(f'共提取 {len(all_items)} 个物品')

    os.makedirs(ONHOLD_DIR, exist_ok=True)
    logger.debug(f'输出目录={ONHOLD_DIR}')

    lines = ['ItemName_EN = {']
    for key in sorted(all_items):
        val = all_items[key].replace('"', '""')
        lines.append(f'\t{key} = "{val}",')
    lines.append('}')
    txt_content = '\n'.join(lines) + '\n'

    txt_path = ONHOLD_DIR / 'ItemName_EN.txt'
    txt_path.write_text(txt_content, encoding='utf-8')
    logger.debug(f'写入 TXT: {txt_path} ({len(txt_content.encode("utf-8"))} 字节)')

    sorted_items = {k: all_items[k] for k in sorted(all_items)}
    json_content = json.dumps(sorted_items, indent='\t', ensure_ascii=False) + '\n'
    json_path = ONHOLD_DIR / 'ItemName.json'
    json_path.write_text(json_content, encoding='utf-8')
    logger.debug(f'写入 JSON: {json_path} ({len(json_content.encode("utf-8"))} 字节)')

    logger.info(f'步骤3完成: 输出到 {ONHOLD_DIR}')
    print(f'  -> {ONHOLD_DIR}')
