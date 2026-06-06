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

## 面板给你哪些数据
- **治理点数** ADM/DIP/MIL、国库/贷款/通胀
- **财政构成**：月收入/支出/净结余，收入来源拆分（税收/生产/贸易/藩属…）、主要支出拆分（来自 `ledger` 月度表，按 rakaly 的索引→类别映射解码）
- **排名**：发展度排名、大国分及排名、是否列强
- 稳定/威望/正统/厌战/腐败/专制度
- 人力/水手、陆军团数/海军船数、陆海传统、力量投射
- 科技 ADM/DIP/MIL 及与全场最高的差距
- 理念组、附庸/属国、盟友、宿敌、谁把你当宿敌、联盟围攻预警、进行中的战争双方

字段名对照 [rakaly/eu4save](https://github.com/rakaly/eu4save) 源码硬编码（`powers`/`treasury`/`manpower`/`ledger.lastmonthincometable` 等），一般不用手动校准。

## 万一某项显示「—」
说明你这版 EU4 某字段名不一样。跑一次把字段名发我对一下即可：
```bat
python eu4_parser.py --keys
```

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
