import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TEMP_DIR
from logger import logger


def run():
    logger.info('手动: 清理temp目录 — 开始')
    logger.debug(f'TEMP_DIR={TEMP_DIR}')

    if not TEMP_DIR.is_dir():
        logger.warn(f'temp 目录不存在: {TEMP_DIR}')
        print(f'temp 目录不存在: {TEMP_DIR}')
        return

    items = list(TEMP_DIR.iterdir())
    logger.debug(f'发现 {len(items)} 个项目待清理')
    deleted_count = 0
    for item in items:
        logger.debug(f'删除: {item.name} ({"目录" if item.is_dir() else "文件"})')
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        deleted_count += 1

    logger.info(f'已清理 {TEMP_DIR} ({deleted_count} 个项目)')
    print(f'已清理 {TEMP_DIR}')
