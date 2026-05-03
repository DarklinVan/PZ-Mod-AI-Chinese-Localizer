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


def _run_step(name, desc):
    print(f'\n{"=" * 50}')
    print(f'  {desc}')
    print(f'{"=" * 50}')
    __import__(f'steps.{name}', fromlist=['run']).run()


def main():
    pipeline = [('collect', '步骤1: 收集EN翻译文件'),
                ('merge',   '步骤2: 合并同名文件'),
                ('items',   '步骤3: 提取物品DisplayName'),
                ('translate', '步骤4: AI翻译')]

    manual_steps = {
        'clean': '手动: 清理temp目录',
    }

    all_steps = dict(pipeline)
    all_steps.update(manual_steps)

    run_all = len(sys.argv) < 2
    target = sys.argv[1].lower() if len(sys.argv) > 1 else None

    if not run_all and target not in all_steps:
        print(f'未知步骤: {target}')
        print(f'流水线步骤: {", ".join(s[0] for s in pipeline)}')
        print(f'手动步骤: {", ".join(manual_steps)}')
        return

    if run_all:
        for name, desc in pipeline:
            _run_step(name, desc)
        print(f'\n{"=" * 50}')
        print('  全部步骤完成!')
    elif target in manual_steps:
        _run_step(target, manual_steps[target])
    else:
        _run_step(target, all_steps[target])


if __name__ == '__main__':
    main()
