"""PZ Mod 汉化工具
用法:
    python main.py              # 运行全部翻译步骤 (collect → merge → items → translate)
    python main.py collect      # 步骤1: 收集EN文件
    python main.py merge        # 步骤2: 合并同名文件
    python main.py items        # 步骤3: 提取物品名称
    python main.py translate    # 步骤4: AI翻译
    python main.py clean        # 手动: 清理temp目录
"""

import sys

from logger import logger


def _run_step(name, desc):
    logger.info(f'步骤开始: {name} — {desc}')
    print(f'\n{"=" * 50}')
    print(f'  {desc}')
    print(f'{"=" * 50}')
    try:
        __import__(f'steps.{name}', fromlist=['run']).run()
        logger.info(f'步骤完成: {name}')
    except Exception as e:
        logger.error(f'步骤失败: {name}', exc_info=True)
        print(f'\n错误: 步骤 {name} 执行失败: {e}')
        raise


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--log-level':
        if len(sys.argv) > 2:
            logger.set_level(sys.argv[2])
        target_args = sys.argv[3:]
    else:
        target_args = sys.argv[1:]

    logger.debug(f'命令行参数: {sys.argv[1:]!r}, 目标步骤: {target_args[0] if target_args else "全部"}')

    pipeline = [('collect', '步骤1: 收集EN翻译文件'),
                ('merge',   '步骤2: 合并同名文件'),
                ('items',   '步骤3: 提取物品DisplayName'),
                ('translate', '步骤4: AI翻译')]

    manual_steps = {
        'clean': '手动: 清理temp目录',
    }

    all_steps = dict(pipeline)
    all_steps.update(manual_steps)

    run_all = len(target_args) < 1
    target = target_args[0].lower() if len(target_args) > 0 else None

    if not run_all and target not in all_steps:
        print(f'未知步骤: {target}')
        print(f'流水线步骤: {", ".join(s[0] for s in pipeline)}')
        print(f'手动步骤: {", ".join(manual_steps)}')
        logger.warn(f'未知步骤名: {target}')
        return

    logger.info(f'启动汉化工具, 日志级别: {logger.level_name}')

    if run_all:
        logger.info('开始全流水线运行')
        for name, desc in pipeline:
            _run_step(name, desc)
        print(f'\n{"=" * 50}')
        print('  全部步骤完成!')
        logger.info('全流水线运行完成')
    elif target in manual_steps:
        _run_step(target, manual_steps[target])
    else:
        _run_step(target, all_steps[target])


if __name__ == '__main__':
    main()
