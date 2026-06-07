# -*- coding: utf-8 -*-
"""调 Claude Code headless (`claude -p`) 当大脑。用你的 CC 订阅，不需要 API key。
- briefing(state, prev): 生成年度战略简报 (返回 dict)
- chat(history, state, briefing): 跟用户聊天 (返回 str)
prompt 通过 stdin 传，避开 Windows 命令行长度限制。
"""
import subprocess, shutil, json, os, re

PERSONA = (
    "你是欧陆风云4(EU4)的随身军师，陪一位玩家打单机普通局。"
    "你拿到的是从存档解析出来的真实游戏数据。"
    "你的风格：直接、实战、像个懂行的老玩家，不啰嗦，给可执行的具体建议"
    "（点哪个科技、跟谁结盟、宣不宣战、怎么压AE、钱花哪），用中文。"
    "不许编造数据里没有的数字。"
)


def _claude_bin():
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _run_claude(prompt, timeout=180):
    """跑 claude -p，返回 (text, error)。"""
    binp = _claude_bin()
    if not binp:
        return None, "找不到 claude 命令。确认 Claude Code 已装且已登录 (`claude` 能在终端跑)。"
    cmd = [binp, "-p", "--output-format", "json"]
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
    except subprocess.TimeoutExpired:
        return None, "Claude 响应超时。"
    except Exception as e:
        return None, f"调用 claude 失败: {e}"
    if proc.returncode != 0:
        return None, f"claude 退出码 {proc.returncode}: {(proc.stderr or '')[:400]}"
    out = (proc.stdout or "").strip()
    # --output-format json -> {"result": "...", "session_id": ...}
    try:
        obj = json.loads(out)
        text = obj.get("result", out)
    except json.JSONDecodeError:
        text = out
    return text, None


def _extract_json(text):
    if not text:
        return None
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    raw = m.group(1) if m else None
    if not raw:
        a, b = text.find('{'), text.rfind('}')
        raw = text[a:b + 1] if a != -1 and b > a else None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _state_brief(state):
    """把状态压成给 Claude 读的简短描述。"""
    s = state
    L = []
    L.append(f"国家: {s.get('player_name')}  日期: {s.get('date')}")
    p = s.get('power') or {}
    L.append(f"治理点数 ADM/DIP/MIL: {p.get('adm')}/{p.get('dip')}/{p.get('mil')}")
    L.append(f"国库: {s.get('treasury')}  贷款: {s.get('loans')}笔/欠{s.get('debt')}  通胀: {s.get('inflation')}")
    econ = s.get('economy') or {}
    if econ:
        line = f"月收支(经常性): 收入 {econ.get('income')} / 支出 {econ.get('expense')} / 净 {econ.get('net')}"
        if econ.get('one_off_income'):
            line += f"  [本月另有一次性入账{econ['one_off_income']}(借款/战利品等,不可持续)]"
        if econ.get('income_top'):
            line += "  经常性收入来源: " + ", ".join(f"{n}{v}" for n, v in econ['income_top'][:4])
        L.append(line)
        if econ.get('expense_top'):
            L.append("主要支出: " + ", ".join(f"{n}{v}" for n, v in econ['expense_top'][:4]))
    L.append(f"稳定: {s.get('stability')}  威望: {s.get('prestige')}  正统: {s.get('legitimacy')}  "
             f"厌战: {s.get('war_exhaustion')}  腐败: {s.get('corruption')}  专制: {s.get('absolutism')}")
    L.append(f"人力: {s.get('manpower')}/{s.get('max_manpower')}  水手: {s.get('sailors')}/{s.get('max_sailors')}  "
             f"陆军: {s.get('regiments')}团  海军: {s.get('ships')}船  陆/海传统: {s.get('army_tradition')}/{s.get('navy_tradition')}")
    t, tm = s.get('tech') or {}, s.get('tech_max') or {}
    L.append(f"科技 ADM/DIP/MIL: {t.get('adm')}/{t.get('dip')}/{t.get('mil')}  "
             f"(全场最高 {tm.get('adm')}/{tm.get('dip')}/{tm.get('mil')})")
    r = s.get('rank') or {}
    L.append(f"发展度: {s.get('development')} (排名 {r.get('dev_rank')}/{r.get('total')})  "
             f"省份: {s.get('num_cities')}  大国分: {r.get('gp_score')}(排名 {r.get('gp_rank')})  力量投射: {s.get('power_projection')}")
    if s.get('subjects'):
        L.append(f"附庸/属国: {s['subjects']}")
    if s.get('ideas'):
        L.append("理念组: " + ", ".join(f"{k}:{v}" for k, v in s['ideas'].items()))
    L.append(f"盟友: {s.get('allies') or '无'}")
    L.append(f"我的宿敌: {s.get('my_rivals') or '无'}  把你当宿敌: {s.get('rivals_me') or '无'}")
    if s.get('coalition'):
        L.append(f"⚠️联盟围攻你: {s['coalition']}")
    if s.get('wars'):
        for w in s['wars']:
            L.append(f"战争[{w['name']}] 我方{w['mine']} vs 敌方{w['enemy']}")
    return "\n".join(L)


def briefing(state, prev=None):
    diff = ""
    if prev:
        diff = ("\n\n【去年同期数据，用于对比/复盘】\n" + _state_brief(prev))
    prompt = f"""{PERSONA}

下面是当前这一年的存档数据：

{_state_brief(state)}{diff}

请生成一张「年度战略简报」。只输出 JSON，不要别的文字，结构如下：
{{
  "headline": "一句话点出当前局势核心(15字内)",
  "review": "对上一年的复盘评价(没有去年数据就写开局判断), 2-3句",
  "situation": "当前局势判断(财政/军事/外交/扩张机会), 2-3句",
  "goals": ["今年1-3个目标, 每条一句, 具体可量化"],
  "watch": ["1-3条需要警惕的风险, 每条一句"],
  "actions": ["3-6条今年具体该做的行动, 每条以动词开头, 很具体"]
}}"""
    text, err = _run_claude(prompt)
    if err:
        return {"error": err}
    data = _extract_json(text)
    if not data:
        return {"error": "Claude 没返回有效 JSON", "raw": (text or "")[:500]}
    return data


def snapshot(state):
    """压成时间线一行(存历史用), 给趋势分析。"""
    e = state.get('economy') or {}
    r = state.get('rank') or {}
    t = state.get('tech') or {}
    return {
        'year': state.get('year'),
        'net': e.get('net'), 'income': e.get('income'),
        'treasury': round(state.get('treasury') or 0),
        'dev': state.get('development'), 'dev_rank': r.get('dev_rank'),
        'gp': r.get('gp_score'),
        'tech': (t.get('adm') or 0) + (t.get('dip') or 0) + (t.get('mil') or 0),
        'mp': state.get('manpower'), 'reg': state.get('regiments'),
    }


def _trend_text(timeline):
    if not timeline:
        return "(本局暂无历史数据，这是第一次分析)"
    rows = ["年份 | 净收 | 国库 | 发展度(名次) | 科技和 | 人力 | 陆军"]
    for s in timeline[-10:]:
        rows.append(f"{s.get('year')} | {s.get('net')} | {s.get('treasury')} | "
                    f"{s.get('dev')}(#{s.get('dev_rank')}) | {s.get('tech')} | {s.get('mp')} | {s.get('reg')}")
    return "\n".join(rows)


def deep_analysis(state, timeline=None):
    """更深入的多维分析(带趋势)，返回结构化 dict 给前端展开。"""
    prompt = f"""{PERSONA}

【当前数据】
{_state_brief(state)}

【历年走势(本局存档时间线)】
{_trend_text(timeline)}

请做一份**深度战略分析**，比快报更狠、更有推理和数字。只输出 JSON，结构如下：
{{
  "trend": "结合上面时间线，判断走向：收入/发展度/科技/排名是在拉开还是被反超？增速如何？2-4句，带具体数字。",
  "economy": "财政深度诊断：收入结构健不健康、靠什么吃饭、钱该砸哪(发展度/建筑/军队/还贷)、有没有隐患。带数字推理，3-4句。",
  "military": "军力评估：团数/科技/传统 vs 周边，战备如何，能不能打、打谁有把握。3-4句。",
  "diplomacy": "外交与威胁：联盟/AE 的数学账、谁最危险、该拉谁抱谁大腿。3-4句。",
  "expansion": "下一步扩张规划：具体打谁、用什么 CB、优先吃哪些方向的省，为什么。3-4句。",
  "plan": ["未来5-10年分阶段路线，3-5条，每条一句带阶段和目标"],
  "verdict": "一句话总评 + 此刻最该做的那一件事"
}}"""
    text, err = _run_claude(prompt)
    if err:
        return {"error": err}
    data = _extract_json(text)
    if not data:
        return {"error": "深度分析没返回有效 JSON", "raw": (text or "")[:500]}
    return data


def chat(history, state, brief=None):
    """history: [{'role':'user'/'assistant','text':...}] 最近若干条。返回回复字符串。"""
    hist_txt = "\n".join(
        ("玩家: " if m['role'] == 'user' else "你: ") + m['text']
        for m in history[-12:]
    )
    brief_txt = ""
    if brief and not brief.get('error'):
        brief_txt = "\n\n【你刚给出的年度简报】\n" + json.dumps(brief, ensure_ascii=False)
    prompt = f"""{PERSONA}

【当前游戏数据】
{_state_brief(state)}{brief_txt}

【对话记录】
{hist_txt}

接着上面对话，以军师身份回复玩家最后一句。直接给内容，不要前缀"你:"，简洁实战。"""
    text, err = _run_claude(prompt)
    if err:
        return f"⚠️ {err}"
    return (text or "").strip() or "（没拿到回复）"
