# PZ Mod 汉化工具集

Project Zomboid 模组本地化（英→中）辅助工具。

## 目录结构

```
.
├── main.py                # 统一入口
├── config.py              # 共享路径/常量
├── steps/                 # 各步骤模块
│   ├── collect.py         #   步骤1: 收集EN翻译文件
│   ├── merge.py           #   步骤2: 合并同名文件
│   ├── items.py           #   步骤3: 提取物品DisplayName
│   └── translate.py       #   步骤4: AI翻译
├── .env                   # 环境变量（API Key，不入库）
├── .env.example           # 环境变量模板
├── .gitignore
├── glossary.txt           # 固定名词翻译对照表
├── prompt.txt             # AI翻译提示词
├── original/              # 原始mod文件（不入库）
├── temp/                  # 中间产物（不入库）
│   ├── <workshopid>/      #   步骤1输出: 收集的EN文件
│   ├── merged/            #   步骤2输出: 合并后的文件
│   └── onhold/            #   步骤3输出: 物品名称文件
└── output/                # 最终翻译输出（不入库）
```

## 环境准备

```powershell
# 创建虚拟环境（如不存在）
python -m venv .venv

# 安装依赖
.venv\Scripts\pip.exe install openai python-dotenv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置 API Key
copy .env.example .env
# 编辑 .env 填入真实 API Key
```

## 使用

### 一站式运行

```powershell
.venv\Scripts\python.exe main.py          # 运行全部4个步骤
```

### 分步运行

```powershell
.venv\Scripts\python.exe main.py collect     # 步骤1: 收集EN文件
.venv\Scripts\python.exe main.py merge       # 步骤2: 合并同名文件
.venv\Scripts\python.exe main.py items       # 步骤3: 提取物品名称
.venv\Scripts\python.exe main.py translate   # 步骤4: AI翻译
```

### 各步骤说明

| 步骤 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `collect` | 从mod提取EN翻译文件 | `original/` | `temp/<wid>/<name>/media/lua/shared/Translate/EN/` |
| `merge` | 合并多mod同名文件 | `temp/<wid>/` | `temp/merged/` |
| `items` | 提取物品DisplayName | `original/` | `temp/onhold/.../ItemName_EN.txt` + `ItemName.json` |
| `translate` | 调用AI翻译 | `temp/merged/` + `temp/onhold/` | `output/` |

## 配置说明

### 环境变量 (`.env`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |

### 固定名词 (`glossary.txt`)

格式: `英文	中文`

翻译时 AI 会严格遵照此表。编辑该文件即可增删词条，无需改代码。

### 黑名单 (`config.py`)

`FILE_BLACKLIST` 集合控制步骤1中不收集的文件（如 `mod.json`）。

## TXT 文件格式规则

- Lua 风格: `VarName = { key = "value", ... }`
- 字符串转义: `""` 表示一个字面双引号
- EN → CN: `xx_EN.txt` → `xx_CN.txt`，变量名同步改为 `_CN`
