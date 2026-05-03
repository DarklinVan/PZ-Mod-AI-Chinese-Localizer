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
│   ├── translate.py       #   步骤4: AI翻译
│   └── clean.py           #   手动: 清理temp目录
├── .env                   # 环境变量（API Key，不入库）
├── .env.example           # 环境变量模板
├── .gitignore
├── glossary.txt           # 固定名词翻译对照表
├── glossary.txt.example   # 固定名词翻译对照表模板
├── prompt.txt             # AI翻译提示词
├── original/              # 原始mod文件（不入库）
├── temp/                  # 中间产物（不入库）
│   ├── <workshopid>/      #   步骤1输出: 收集的EN文件
│   ├── merged/            #   步骤2输出: 合并后的文件
│   ├── onhold/            #   步骤3输出: 物品名称文件
│   └── translate_cache.json # 翻译缓存（增量翻译）
└── output/                # 最终翻译输出（不入库）
```

## 环境准备

```powershell
# 安装依赖
pip install openai python-dotenv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置 API Key
copy .env.example .env
# 编辑 .env 填入真实 API Key
```

## 使用

### 一站式运行

```powershell
python.exe main.py              # collect → merge → items → translate
```

### 分步运行

```powershell
python.exe main.py collect      # 步骤1: 收集EN文件
python.exe main.py merge        # 步骤2: 合并同名文件
python.exe main.py items        # 步骤3: 提取物品DisplayName
python.exe main.py translate    # 步骤4: AI翻译
python.exe main.py clean        # 手动: 清理temp目录
```

### 各步骤说明

| 步骤 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `collect` | 从mod提取EN翻译文件（大小写不敏感） | `original/` | `temp/<wid>/<name>/.../EN/` |
| `merge` | 合并多mod同名文件,txt加分隔符,json合并去重 | `temp/<wid>/` | `temp/merged/` |
| `items` | 提取`module.itemid`与DisplayName | `original/` | `temp/onhold/.../ItemName_EN.txt` + `.json` |
| `translate` | AI翻译，先查缓存仅调未命中词条 | `temp/merged/` + `temp/onhold/` | `output/` |
| `clean` | 清空 `temp/`（手动执行，不在流水线中） | `temp/` | — |

### 增量翻译

步骤4首次运行后会在 `temp/` 生成 `translate_cache.json`。后续再次翻译时：
- 命中缓存 → 直接使用，不调用API
- 未命中 → 仅翻译新增词条，更新缓存

清除缓存：`python main.py clean`

## 配置说明

### 环境变量 (`.env`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |
| `TRANSLATE_BATCH_SIZE` | 每批翻译词条数 | `200` |

### 固定名词 (`glossary.txt`)

格式: `英文	中文`（Tab 分隔），`#` 开头为注释。

翻译时 AI 会严格遵照此表。编辑该文件即可增删词条，无需改代码。

涵盖分类：车辆品牌/型号、军事/警察、迷彩/制服、车辆部件、服装类、UI动作、配方/制作等，共 250+ 条。

### 翻译提示词 (`prompt.txt`)

独立存放 AI 翻译的 system prompt，`{glossary}` 占位符会在运行时替换为 glossary.txt 的实际内容。

### 黑名单 (`config.py`)

`FILE_BLACKLIST` 集合控制步骤1中不收集的文件（如 `mod.json`）。

### 半角符号归一化

AI 翻译后的中文全角标点（，；：（）等）会自动转为英文半角，确保游戏引擎兼容。

## 文件格式说明

### TXT 格式（Lua 风格）

```lua
VarName_EN = {
    key = "value",
}
```

- 字符串转义: `""` 表示一个字面双引号
- EN → CN: `xx_EN.txt` → `xx_CN.txt`，变量名 `_EN` → `_CN`

### JSON 格式

```json
{
    "key": "value"
}
```

- `xx_EN.json` → `xx_CN.json`，不带 `_EN` 的文件名不变
- 与TXT共享同一套翻译，仅替换value

### 物品定义解析

从 `media\Scripts\**\*.txt` 中提取：
```
module Base
{
    item SomeItem
    {
        DisplayName = "Item Name",
    }
}
```
→ `Base.SomeItem` = `Item Name`
