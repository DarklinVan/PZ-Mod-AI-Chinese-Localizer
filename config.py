from pathlib import Path

ROOT = Path(__file__).parent

ORIGINAL_DIR = ROOT / 'original'
TEMP_DIR = ROOT / 'temp'
MERGED_DIR = TEMP_DIR / 'merged'
ONHOLD_DIR = TEMP_DIR / 'onhold' / 'media' / 'lua' / 'shared' / 'Translate' / 'EN'
OUTPUT_DIR = ROOT / 'output'
TRANSLATE_CACHE_FILE = TEMP_DIR / 'translate_cache.json'

PROMPT_FILE = ROOT / 'prompt.txt'
GLOSSARY_FILE = ROOT / 'glossary.txt'
ENV_FILE = ROOT / '.env'

TRANSLATE_EN = Path('media', 'lua', 'shared', 'Translate', 'EN')

FILE_BLACKLIST = {'mod.json'}
