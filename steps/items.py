import json
import os
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ORIGINAL_DIR, ONHOLD_DIR

ITEM_BLOCK_RE = re.compile(
    r'^\s*item\s+(\S+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
    re.MULTILINE
)
DISPLAYNAME_RE = re.compile(r'DisplayName\s*=\s*(.+?),?\s*$', re.MULTILINE)
MODULE_RE = re.compile(r'^\s*module\s+(\S+)\s*\{', re.MULTILINE)


def _extract(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    mod_m = MODULE_RE.search(text)
    module_name = mod_m.group(1) if mod_m else ''

    items = {}
    for m in ITEM_BLOCK_RE.finditer(text):
        name = m.group(1)
        block = m.group(2)
        dn = DISPLAYNAME_RE.search(block)
        if dn:
            val = dn.group(1).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            items[f'{module_name}.{name}'] = val
    return items


def run():
    all_items = {}

    for wid in sorted(os.listdir(ORIGINAL_DIR)):
        wspath = ORIGINAL_DIR / wid
        if not wspath.is_dir():
            continue

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

            for fn in files:
                if not fn.lower().endswith('.txt'):
                    continue
                items = _extract(rp / fn)
                if items:
                    all_items.update(items)

    if not all_items:
        print('未找到任何物品')
        return

    print(f'共提取 {len(all_items)} 个物品')

    os.makedirs(ONHOLD_DIR, exist_ok=True)

    lines = ['ItemName_EN = {']
    for key in sorted(all_items):
        val = all_items[key].replace('"', '""')
        lines.append(f'\t{key} = "{val}",')
    lines.append('}')

    (ONHOLD_DIR / 'ItemName_EN.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    sorted_items = {k: all_items[k] for k in sorted(all_items)}
    (ONHOLD_DIR / 'ItemName.json').write_text(
        json.dumps(sorted_items, indent='\t', ensure_ascii=False) + '\n',
        encoding='utf-8'
    )

    print(f'  -> {ONHOLD_DIR}')
