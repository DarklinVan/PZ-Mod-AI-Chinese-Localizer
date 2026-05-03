import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TEMP_DIR


def run():
    if not TEMP_DIR.is_dir():
        print(f'temp 目录不存在: {TEMP_DIR}')
        return

    for item in TEMP_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print(f'已清理 {TEMP_DIR}')
