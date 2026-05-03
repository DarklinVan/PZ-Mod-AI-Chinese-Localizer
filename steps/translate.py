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
from logger import logger

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
                cache = {k: v for k, v in json.load(f).items() if k}
                logger.debug(f'缓存加载: {len(cache)} 条, 文件={TRANSLATE_CACHE_FILE}')
                return cache
        except (json.JSONDecodeError, OSError) as e:
            logger.warn(f'缓存加载失败: {e}')
            pass
    logger.debug('缓存文件不存在，返回空')
    return {}


def _save_cache(cache):
    cache = {k: v for k, v in cache.items() if k}
    logger.debug(f'缓存保存: {len(cache)} 条, 去空键后 {len(cache)} 条')
    TRANSLATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRANSLATE_CACHE_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent='\t')
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(TRANSLATE_CACHE_FILE)


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
    logger.debug(f'_parse_txt: {filepath.name} ({len(lines)} 行)')

    for i, line in enumerate(lines):
        if header is None:
            bi = line.find('{')
            if bi >= 0:
                header = line[:bi].strip()
                logger.debug(f'_parse_txt: header={header!r}')
            continue
        if '}' in line.strip() and i >= len(lines) - 2:
            logger.debug(f'_parse_txt: 在第 {i+1} 行遇到闭合括号，结束')
            break

        kv = _parse_txt_kv(line)
        if kv:
            items.append(('kv', kv[0], kv[1]))
        elif TXT_SEP_RE.match(line):
            items.append(('sep', line.strip()))
    kv_count = sum(1 for it in items if it[0] == 'kv')
    sep_count = sum(1 for it in items if it[0] == 'sep')
    logger.debug(f'_parse_txt: 共 {len(items)} 项 (kv={kv_count}, sep={sep_count})')
    return header, items


def _cn_header(header, filename):
    vn = header.rstrip('{').strip()
    if vn.endswith('='):
        vn = vn[:-1].strip()
    logger.debug(f'_cn_header: header={header!r}, filename={filename!r}, vn={vn!r}')

    cn = re.sub(r'_EN$', '_CN', vn)
    if cn == vn:
        cn = re.sub(r'EN$', '_CN', vn)
    if cn == vn:
        m = re.match(r'^(.*)_EN\.txt$', filename, re.IGNORECASE)
        if m:
            cn = m.group(1) + '_CN'
    result = header.replace(vn, cn, 1)
    logger.debug(f'_cn_header: result={result!r}')
    return result


def _batch(values, n=200):
    for i in range(0, len(values), n):
        yield values[i:i + n]


def _call_api(client, model, sp, batch, max_tokens):
    user = '\n'.join(f'{json.dumps(v, ensure_ascii=False)}: ""' for v in batch)
    logger.debug(f'API调用: model={model}, batch_size={len(batch)}, max_tokens={max_tokens}, user_preview={user[:200]}...')
    for attempt in range(3):
        content = ''
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': sp},
                    {'role': 'user', 'content': user},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content.strip()
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)
            parsed = json.loads(content)
            logger.debug(f'API调用成功: 返回 {len(parsed)} 条翻译')
            return parsed
        except json.JSONDecodeError:
            tail = content[-200:] if len(content) > 200 else content
            logger.warn(f'JSON解析失败 (尝试 {attempt+1}), 响应长度={len(content)}, 尾部: {tail}')
            print(f'  JSON解析失败 (尝试 {attempt + 1}), 响应尾部: {tail}')
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            logger.error(f'API调用失败 (尝试 {attempt+1}): {e}')
            print(f'  API调用失败 (尝试 {attempt + 1}): {e}')
            if attempt < 2:
                time.sleep(2 ** attempt)
    logger.warn(f'API调用全部重试失败, 批次 {len(batch)} 条翻译丢失')
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
    logger.info('步骤4: AI翻译 — 开始')
    load_dotenv(ROOT / '.env')

    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    batch_size = int(os.getenv('TRANSLATE_BATCH_SIZE', '200'))
    max_tokens = int(os.getenv('TRANSLATE_MAX_TOKENS', '16384'))

    logger.debug(f'配置: model={model}, batch_size={batch_size}, max_tokens={max_tokens}')

    if not api_key or api_key == 'sk-your-deepseek-api-key':
        logger.error('.env 中未设置 DEEPSEEK_API_KEY')
        print('请先在 .env 中设置 DEEPSEEK_API_KEY')
        return

    sp = _build_system_prompt()
    if not sp:
        logger.error('prompt.txt 为空')
        print('prompt.txt 为空')
        return
    logger.debug(f'system_prompt 长度: {len(sp)} 字符')

    client = OpenAI(api_key=api_key, base_url=base_url)

    src_dirs = [MERGED_DIR]
    if ONHOLD_DIR.is_dir():
        src_dirs.append(ONHOLD_DIR)
    logger.debug(f'源目录: {[str(d) for d in src_dirs]}')

    txt_files, json_files = [], []
    for sd in src_dirs:
        txt_files.extend(sorted(sd.glob('*.txt')))
        json_files.extend(sorted(sd.glob('*.json')))

    if not txt_files and not json_files:
        logger.warn('merged 和 onhold 目录均无文件')
        print('merged 和 onhold 目录均无文件')
        return

    print(f'模型: {model}')
    print('解析文件...')
    logger.debug(f'源文件: {len(txt_files)} 个TXT, {len(json_files)} 个JSON')

    all_values = set()
    txt_entries = []
    json_entries = []

    for f in txt_files:
        h, items = _parse_txt(f)
        txt_entries.append((f.name, h, items))
        kv_count = sum(1 for it in items if it[0] == 'kv')
        all_values.update(v for it in items if it[0] == 'kv' and it[2] for v in [it[2]])
        logger.debug(f'  TXT {f.name}: {kv_count} 条kv')
        print(f'  TXT  {f.name}  ({kv_count} 条, header="{h}")')

    for f in json_files:
        with open(f, encoding='utf-8', errors='replace') as fh:
            data = json.load(fh)
        json_entries.append((f.name, data))
        all_values.update(v for v in data.values() if v)
        logger.debug(f'  JSON {f.name}: {len(data)} 条, {sum(1 for v in data.values() if not v)} 条空值已过滤')
        print(f'  JSON {f.name}  ({len(data)} 条)')

    vals = sorted(all_values, key=lambda x: (len(x), x))
    logger.debug(f'总唯一值: {len(vals)}')
    print(f'\n共 {len(vals)} 条唯一文本待翻译')

    cache = _load_cache()
    translations = {k: v for k, v in cache.items() if k in all_values}
    cached_count = len(translations)
    if cached_count:
        logger.debug(f'缓存命中: {cached_count}/{len(vals)} = {cached_count/len(vals)*100:.1f}%')
        print(f'  其中 {cached_count} 条命中缓存')

    uncached = [v for v in vals if v not in translations]
    if uncached:
        logger.info(f'需调用AI翻译 {len(uncached)} 条 (未命中比例 {len(uncached)/len(vals)*100:.1f}%)')
        print(f'  需调用AI翻译 {len(uncached)} 条')
        for bi, batch in enumerate(_batch(uncached, batch_size), 1):
            s = (bi - 1) * batch_size + 1
            e = min(bi * batch_size, len(uncached))
            logger.debug(f'批次 {bi}: 范围 {s}-{e}')
            print(f'\n翻译批次 {bi} ({s}-{e}/{len(uncached)})...')
            r = _call_api(client, model, sp, batch, max_tokens)
            translations.update(r)
            cache.update(r)
            logger.debug(f'批次 {bi} 获得 {len(r)} 条翻译')
            print(f'  获得 {len(r)} 条翻译')

        _save_cache(cache)
        logger.info(f'缓存已更新 (共 {len(cache)} 条)')
        print(f'  缓存已更新 (共 {len(cache)} 条)')
    else:
        logger.info('全部命中缓存, 无需调用AI')
        print('  全部命中缓存, 无需调用AI')

    translations = {k: _normalize_punct(v) for k, v in translations.items()}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f'\n生成输出到 {OUTPUT_DIR}...')

    txt_groups = {}
    for fn, h, items in txt_entries:
        ch = _cn_header(h, fn)
        cn_name = re.sub(r'_EN\.txt$', '_CN.txt', fn, flags=re.IGNORECASE)
        if cn_name not in txt_groups:
            txt_groups[cn_name] = {'header': ch, 'items': []}
        for it in items:
            if it[0] == 'kv':
                _, k, v = it
                translated = translations.get(v, v)
                txt_groups[cn_name]['items'].append(('kv', k, translated))
            elif it[0] == 'sep':
                txt_groups[cn_name]['items'].append(it)
    logger.debug(f'TXT 输出分组: {len(txt_groups)} 个文件')
    for cn_name, grp in sorted(txt_groups.items()):
        kv_count = sum(1 for it in grp['items'] if it[0] == 'kv')
        content = _fmt_txt(grp['header'], grp['items'])
        (OUTPUT_DIR / cn_name).write_text(content, encoding='utf-8')
        logger.debug(f'写入 TXT {cn_name}: {kv_count} 条 ({len(content.encode("utf-8"))} 字节)')
        print(f'  TXT  {cn_name}')

    json_groups = {}
    for fn, data in json_entries:
        cn_name = re.sub(r'_EN\.json$', '_CN.json', fn, flags=re.IGNORECASE)
        cd = json_groups.setdefault(cn_name, {})
        for k, v in data.items():
            cd[k] = translations.get(v, v)

    logger.debug(f'JSON 输出分组: {len(json_groups)} 个文件')
    for cn_name in sorted(json_groups):
        cd = json_groups[cn_name]
        content = json.dumps(cd, indent='\t', ensure_ascii=False) + '\n'
        (OUTPUT_DIR / cn_name).write_text(content, encoding='utf-8')
        logger.debug(f'写入 JSON {cn_name}: {len(cd)} 条 ({len(content.encode("utf-8"))} 字节)')
        print(f'  JSON {cn_name}')

    missing = sum(1 for v in all_values if v not in translations)
    if missing:
        print(f'\n注意: {missing} 条文本未翻译，已保留原文')

    logger.info(f'步骤4完成: 共处理 {len(txt_groups)} 个TXT + {len(json_groups)} 个JSON')
    print(f'\n完成! 共处理 {len(txt_groups)} 个TXT + {len(json_groups)} 个JSON')
