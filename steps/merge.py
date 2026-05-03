import json
import os
import re
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import TEMP_DIR, MERGED_DIR, TRANSLATE_EN


def _collect():
    groups = {}
    for wid in os.listdir(TEMP_DIR):
        wspath = os.path.join(TEMP_DIR, wid)
        if not os.path.isdir(wspath) or wid in ('merged', 'onhold'):
            continue
        for mod_id in os.listdir(wspath):
            en_path = os.path.join(wspath, mod_id, TRANSLATE_EN)
            if not os.path.isdir(en_path):
                continue
            for fn in os.listdir(en_path):
                fp = os.path.join(en_path, fn)
                if not os.path.isfile(fp):
                    continue
                groups.setdefault(fn, []).append((fp, wid, mod_id))
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
        if header is None:
            header = _txt_header(text, fn)
        parts.append(_sep(mod_id, wid, indent='\t'))
        parts.append(_normalize(_inner(text)).rstrip(','))
    return f'{header} {{\n' + '\n'.join(parts) + '\n}\n'


def _merge_json(infos):
    merged = {}
    for fp, wid, mod_id in infos:
        with open(fp, encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        merged.update(data)
    return json.dumps(merged, indent='\t', ensure_ascii=False) + '\n'


def run():
    groups = _collect()
    if not groups:
        print('未找到任何文件')
        return

    os.makedirs(MERGED_DIR, exist_ok=True)
    total = 0

    for fn, infos in sorted(groups.items()):
        ext = os.path.splitext(fn)[1].lower()
        if ext == '.txt':
            merged = _merge_txt(infos)
        elif ext == '.json':
            merged = _merge_json(infos)
        else:
            continue

        with open(os.path.join(MERGED_DIR, fn), 'w', encoding='utf-8') as f:
            f.write(merged)

        print(f'[{fn}] {len(infos)} 个文件 -> merged')
        total += 1

    print(f'\n完成! 共合并 {total} 个文件到 {MERGED_DIR}')
