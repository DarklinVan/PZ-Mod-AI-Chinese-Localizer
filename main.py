"""PZ Mod 汉化工具
用法:
    python main.py              # 运行全部步骤
    python main.py collect      # 步骤1: 收集EN文件
    python main.py merge        # 步骤2: 合并同名文件
    python main.py items        # 步骤3: 提取物品名称
    python main.py translate    # 步骤4: AI翻译
    python main.py clean        # 步骤5: 清理temp
"""

import sys


def main():
    steps = [('collect', '步骤1: 收集EN翻译文件'),
             ('merge',   '步骤2: 合并同名文件'),
             ('items',   '步骤3: 提取物品DisplayName'),
             ('translate', '步骤4: AI翻译'),
             ('clean',   '步骤5: 清理temp目录')]

    run_all = len(sys.argv) < 2
    target = sys.argv[1].lower() if len(sys.argv) > 1 else None

    valid = {s[0] for s in steps}
    if not run_all and target not in valid:
        print(f'未知步骤: {target}')
        print(f'可用步骤: {", ".join(valid)}')
        return

    for step_name, step_desc in steps:
        if not run_all and step_name != target:
            continue

        print(f'\n{"=" * 50}')
        print(f'  {step_desc}')
        print(f'{"=" * 50}')

        mod = __import__(f'steps.{step_name}', fromlist=['run'])
        mod.run()

    if run_all:
        print(f'\n{"=" * 50}')
        print('  全部步骤完成!')


if __name__ == '__main__':
    main()
