import json
import os
import re
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from openai import OpenAI

from config import MERGED_DIR, ONHOLD_DIR, OUTPUT_DIR, TRANSLATE_CACHE_FILE, PROMPT_FILE, GLOSSARY_FILE, ROOT

TXT_KV_KEY_RE = re.compile(r'^\s*([^\s=]+)\s*=\s*"')
TXT_SEP_RE = re.compile(r'^\s*-{10,}.*-{10,}\s*$')

_CN_PUNCT = str.maketrans({
    '（': '(', '）': ')', '，': ',', '；': ';',
    '：': ':', '！': '!', '？': '?', '。': '.',
    '“': '"', '”': '"', '‘': "'", '’': "'",
})


def _normalize_punct(text):
    return text.translate(_CN_PUNCT)


def _load_cache():
    if TRANSLATE_CACHE_FILE.exists():
        try:
            with open(TRANSLATE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache):
    TRANSLATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRANSLATE_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent='\t')
def _parse_lua_string(s, start):
    i = start + 1
    result = []
    while i < len(s):
        if s[i] == '"':
            if i + 1 < len(s) and s[i + 1] == '"':
                result.append('"')
                i += 2
            else:
                return ''.join(result), i + 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result), i


def _parse_txt_kv(line):
    m = TXT_KV_KEY_RE.match(line)
    if not m:
        return None
    key = m.group(1)
    val, _ = _parse_lua_string(line, m.end() - 1)
    return key, val


def _load_prompt():
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding='utf-8').strip()
    return ''


def _load_glossary():
    if not GLOSSARY_FILE.exists():
        return ''
    lines = []
    for line in GLOSSARY_FILE.read_text(encoding='utf-8').split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if '\t' in s:
            en, cn = s.split('\t', 1)
            lines.append(f'  {en.strip()} → {cn.strip()}')
    if not lines:
        return ''
    return '固定名词对照表：\n' + '\n'.join(lines)


def _build_system_prompt():
    prompt = _load_prompt()
    glossary = _load_glossary()
    if '{glossary}' in prompt and glossary:
        return prompt.replace('{glossary}', glossary)
    elif '{glossary}' in prompt:
        return prompt.replace('{glossary}', '')
    elif glossary:
        return prompt + '\n\n' + glossary
    return prompt


def _parse_txt(filepath):
    header = None
    items = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if header is None:
            bi = line.find('{')
            if bi >= 0:
                header = line[:bi].strip()
            continue
        if '}' in line.strip() and i >= len(lines) - 2:
            break

        kv = _parse_txt_kv(line)
        if kv:
            items.append(('kv', kv[0], kv[1]))
        elif TXT_SEP_RE.match(line):
            items.append(('sep', line.strip()))
    return header, items


def _cn_header(header, filename):
    vn = header.rstrip('{').strip()
    if vn.endswith('='):
        vn = vn[:-1].strip()

    cn = re.sub(r'_EN$', '_CN', vn)
    if cn == vn:
        cn = re.sub(r'EN$', '_CN', vn)
    if cn == vn:
        m = re.match(r'^(.*)_EN\.txt$', filename, re.IGNORECASE)
        if m:
            cn = m.group(1) + '_CN'
    return header.replace(vn, cn, 1)


def _batch(values, n=200):
    for i in range(0, len(values), n):
        yield values[i:i + n]


def _call_api(client, model, sp, batch):
    user = '\n'.join(f'{json.dumps(v, ensure_ascii=False)}: ""' for v in batch)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': sp},
                    {'role': 'user', 'content': user},
                ],
                temperature=0.1,
                max_tokens=8192,
            )
            content = resp.choices[0].message.content.strip()
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)
            return json.loads(content)
        except json.JSONDecodeError:
            print(f'  JSON解析失败 (尝试 {attempt + 1})')
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            print(f'  API调用失败 (尝试 {attempt + 1}): {e}')
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {}


def _rm_empty_seps(items):
    cleaned, pending = [], []
    for item in items:
        if item[0] == 'sep':
            pending.append(item)
        else:
            cleaned.extend(pending)
            pending.clear()
            cleaned.append(item)
    return cleaned


def _fmt_txt(header, items):
    items = _rm_empty_seps(items)
    lines = [f'{header} {{']
    for item in items:
        if item[0] == 'kv':
            _, k, v = item
            lines.append(f'\t{k} = "{v.replace(chr(34), chr(34)*2)}",')
        elif item[0] == 'sep':
            lines.append(f'\t{item[1]}')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def run():
    load_dotenv(ROOT / '.env')

    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    batch_size = int(os.getenv('TRANSLATE_BATCH_SIZE', '200'))

    if not api_key or api_key == 'sk-your-deepseek-api-key':
        print('请先在 .env 中设置 DEEPSEEK_API_KEY')
        return

    sp = _build_system_prompt()
    if not sp:
        print('prompt.txt 为空')
        return

    client = OpenAI(api_key=api_key, base_url=base_url)

    src_dirs = [MERGED_DIR]
    if ONHOLD_DIR.is_dir():
        src_dirs.append(ONHOLD_DIR)

    txt_files, json_files = [], []
    for sd in src_dirs:
        txt_files.extend(sorted(sd.glob('*.txt')))
        json_files.extend(sorted(sd.glob('*.json')))

    if not txt_files and not json_files:
        print('merged 和 onhold 目录均无文件')
        return

    print(f'模型: {model}')
    print('解析文件...')

    all_values = set()
    txt_entries = []
    json_entries = []

    for f in txt_files:
        h, items = _parse_txt(f)
        txt_entries.append((f.name, h, items))
        kv_count = sum(1 for it in items if it[0] == 'kv')
        all_values.update(v for it in items if it[0] == 'kv' for v in [it[2]])
        print(f'  TXT  {f.name}  ({kv_count} 条, header="{h}")')

    for f in json_files:
        with open(f, encoding='utf-8', errors='replace') as fh:
            data = json.load(fh)
        json_entries.append((f.name, data))
        all_values.update(data.values())
        print(f'  JSON {f.name}  ({len(data)} 条)')

    vals = sorted(all_values, key=lambda x: (len(x), x))
    print(f'\n共 {len(vals)} 条唯一文本待翻译')

    cache = _load_cache()
    translations = {k: v for k, v in cache.items() if k in all_values}
    cached_count = len(translations)
    if cached_count:
        print(f'  其中 {cached_count} 条命中缓存')

    uncached = [v for v in vals if v not in translations]
    if uncached:
        print(f'  需调用AI翻译 {len(uncached)} 条')
        for bi, batch in enumerate(_batch(uncached, batch_size), 1):
            s = (bi - 1) * batch_size + 1
            e = min(bi * batch_size, len(uncached))
            print(f'\n翻译批次 {bi} ({s}-{e}/{len(uncached)})...')
            r = _call_api(client, model, sp, batch)
            translations.update(r)
            cache.update(r)
            print(f'  获得 {len(r)} 条翻译')

        _save_cache(cache)
        print(f'  缓存已更新 (共 {len(cache)} 条)')
    else:
        print('  全部命中缓存, 无需调用AI')

    translations = {k: _normalize_punct(v) for k, v in translations.items()}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f'\n生成输出到 {OUTPUT_DIR}...')

    for fn, h, items in txt_entries:
        ch = _cn_header(h, fn)
        ci = []
        for it in items:
            if it[0] == 'kv':
                _, k, v = it
                ci.append(('kv', k, translations.get(v, v)))
            elif it[0] == 'sep':
                ci.append(it)

        cn_name = re.sub(r'_EN\.txt$', '_CN.txt', fn, flags=re.IGNORECASE)
        (OUTPUT_DIR / cn_name).write_text(_fmt_txt(ch, ci), encoding='utf-8')
        print(f'  TXT  {fn} -> {cn_name}')

    for fn, data in json_entries:
        cd = {k: translations.get(v, v) for k, v in data.items()}
        cn_name = re.sub(r'_EN\.json$', '_CN.json', fn, flags=re.IGNORECASE)
        (OUTPUT_DIR / cn_name).write_text(
            json.dumps(cd, indent='\t', ensure_ascii=False) + '\n',
            encoding='utf-8'
        )
        print(f'  JSON {fn} -> {cn_name}')

    missing = sum(1 for v in all_values if v not in translations)
    if missing:
        print(f'\n注意: {missing} 条文本未翻译，已保留原文')

    print(f'\n完成! 共处理 {len(txt_entries)} 个TXT + {len(json_entries)} 个JSON')
