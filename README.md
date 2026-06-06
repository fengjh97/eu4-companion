# EU4 陪玩军师面板

贴在欧陆风云4旁边的常驻面板：每次存档自动刷新「年度战略简报」（上年复盘 / 局势 / 今年目标 / 注意 / 行动清单），下面能跟军师聊天决定下一步。后端用 **Claude Code headless (`claude -p`)** 当大脑，**不需要 API key**，用你现成的 Claude Code 订阅。

```
EU4 存档(.eu4) ──watch──▶ Python后端 ──解析──▶ 状态JSON ──claude -p──▶ 简报/对话 ──ws──▶ 网页面板
```

## 前提（Windows）
- Python（你的 miniconda 就行）
- Claude Code 已安装并登录：终端能跑 `claude` 且 `claude -p "hi"` 有回应
- 普通局、**非铁人(Ironman)**。建议游戏设置里把自动存档设成「每年」

## 安装 & 跑
```bat
cd eu4-companion
pip install -r requirements.txt
run.bat
```
`run.bat` 会起后端 + 用 Chrome 开一个干净的 app 小窗口。
想置顶贴在游戏上：游戏开「无边框窗口化」，再右键 `pin_topmost.ps1` → 用 PowerShell 运行。

## ⚠️ 第一次先校准字段
不同 EU4 版本字段名可能略有出入。先跑一次：
```bat
python eu4_parser.py --keys
```
把输出整段发回给 Claude（我），对一遍真实字段名，把对不上的（比如 powers/treasury/manpower）修一下，再正式用。

## 文件
- `eu4_parser.py` — 存档解析 + 状态抽取（零依赖）
- `claude_bridge.py` — 调 `claude -p` 生成简报 / 聊天
- `server.py` — FastAPI 后端：监测存档 + WebSocket
- `web/index.html` — 面板前端
- `run.bat` / `pin_topmost.ps1` — 启动 / 置顶

## 跟同类项目的区别
EU4 的「读存档 → 展示数据」工具已经很多（[pdx-tools](https://github.com/pdx-tools/pdx-tools)、[rakaly/eu4save](https://github.com/rakaly/eu4save)、各种 clausewitz parser、EuropaWarAnalyzer…）。
本项目不一样的地方：**不止展示数据，而是把存档喂给 LLM（Claude Code）当随身军师**——每年自动给你一张战略简报（复盘/目标/行动清单）+ 能对话决策。解析部分故意做成零依赖的轻量 Python 版，够喂模型即可，不追求像 rakaly 那样面面俱到。这个「LLM 实时陪玩军师面板」的角度目前在开源里基本是空白。

## 常见问题
- **找不到存档夹**：`set EU4_SAVE_DIR=...` 或 `python -m uvicorn server:app --port 8777` 前设环境变量
- **铁人存档读不了**：关掉 Ironman，或用 rakaly melt 转明文
- **claude 调用失败**：确认 `claude` 在 PATH、已登录、`claude -p "测试"` 能出字
