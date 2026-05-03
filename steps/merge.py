import json
import os
import re
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import TEMP_DIR, MERGED_DIR, TRANSLATE_EN
from logger import logger


def _collect():
    groups = {}
    for wid in os.listdir(TEMP_DIR):
        wspath = os.path.join(TEMP_DIR, wid)
        if not os.path.isdir(wspath) or wid in ('merged', 'onhold'):
            logger.debug(f'_collect: 跳过 {wid} (非目录或排除目录)')
            continue
        for mod_id in os.listdir(wspath):
            en_path = os.path.join(wspath, mod_id, TRANSLATE_EN)
            if not os.path.isdir(en_path):
                logger.debug(f'_collect: {wid}/{mod_id} — Translate/EN 不存在')
                continue
            files_found = os.listdir(en_path)
            logger.debug(f'_collect: {wid}/{mod_id} — 发现 {len(files_found)} 个文件')
            for fn in files_found:
                fp = os.path.join(en_path, fn)
                if not os.path.isfile(fp):
                    continue
                groups.setdefault(fn, []).append((fp, wid, mod_id))
                logger.debug(f'_collect: 分组 {fn} <- {wid}/{mod_id}')
    return groups


def _inner(text):
    a = text.find('{')
    if a == -1:
        return text.strip()
    b = text.rfind('}')
    if b == -1:
        return text[a + 1:].strip()
    return text[a + 1:b].strip()


def _normalize(text):
    lines = []
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('/*') or s.startswith('*') or s.startswith('//'):
            continue
        lines.append('\t' + s if s else '')
    return '\n'.join(lines)


def _txt_header(text, filename):
    idx = text.find('{')
    if idx == -1:
        m = re.match(r'^(.*)_EN\.txt$', filename, re.IGNORECASE)
        if m:
            return m.group(1) + '_EN'
        return os.path.splitext(filename)[0]
    return text[:idx].strip()


def _sep(mod_id, workshop_id, indent=''):
    return f'{indent}--------------------{mod_id}({workshop_id})--------------------'


def _merge_txt(infos):
    header = None
    parts = []
    for fp, wid, mod_id in infos:
        fn = os.path.basename(fp)
        text = open(fp, encoding='utf-8', errors='replace').read()
        logger.debug(f'_merge_txt: 读取 {fn} ({len(text)} 字符)')
        if header is None:
            header = _txt_header(text, fn)
            logger.debug(f'_merge_txt: header={header!r}')
        parts.append(_sep(mod_id, wid, indent='\t'))
        inner = _normalize(_inner(text)).rstrip(',')
        inner_lines = inner.count('\n') + 1
        logger.debug(f'_merge_txt: {fn} 内部内容 {inner_lines} 行')
        parts.append(inner)
    result = f'{header} {{\n' + '\n'.join(parts) + '\n}\n'
    logger.debug(f'_merge_txt: 合并结果 {len(result)} 字符')
    return result


def _merge_json(infos):
    merged = {}
    for fp, wid, mod_id in infos:
        with open(fp, encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        logger.debug(f'_merge_json: {os.path.basename(fp)} — {len(data)} 条')
        merged.update(data)
    logger.debug(f'_merge_json: 合并后共 {len(merged)} 条')
    return json.dumps(merged, indent='\t', ensure_ascii=False) + '\n'


def run():
    logger.info('步骤2: 合并同名文件 — 开始')

    groups = _collect()
    if not groups:
        logger.warn('未找到任何文件')
        print('未找到任何文件')
        return
    logger.debug(f'_collect 结果: {len(groups)} 个分组')
    for fn, infos in sorted(groups.items()):
        logger.debug(f'  分组 [{fn}]: {len(infos)} 个来源')

    os.makedirs(MERGED_DIR, exist_ok=True)
    total = 0

    for fn, infos in sorted(groups.items()):
        ext = os.path.splitext(fn)[1].lower()
        logger.debug(f'处理 [{fn}] (ext={ext})')
        try:
            if ext == '.txt':
                merged = _merge_txt(infos)
            elif ext == '.json':
                merged = _merge_json(infos)
            else:
                continue
        except Exception as e:
            logger.error(f'合并失败 [{fn}]', exc_info=True)
            print(f'[错误] {fn}: {e}')
            continue

        with open(os.path.join(MERGED_DIR, fn), 'w', encoding='utf-8') as f:
            f.write(merged)

        merged_size = len(merged.encode('utf-8'))
        logger.debug(f'[写入] {fn} ({merged_size} 字节)')
        logger.info(f'[{fn}] {len(infos)} 个文件 -> merged')
        print(f'[{fn}] {len(infos)} 个文件 -> merged')
        total += 1

    logger.info(f'步骤2完成: 共合并 {total} 个文件')
    print(f'\n完成! 共合并 {total} 个文件到 {MERGED_DIR}')
