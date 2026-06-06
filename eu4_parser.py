# -*- coding: utf-8 -*-
"""EU4 普通局存档解析 + 状态抽取 (零第三方依赖)。
被 server.py 调用; 也能单独 `python eu4_parser.py <save> --keys` 调试字段名。
铁人(EU4bin)存档读不了, 需先 rakaly melt。
"""
import sys, os, re, zipfile, glob, json

sys.setrecursionlimit(1000000)  # 存档嵌套很深(省份历史等)

# 操作符两字符在前, 再单字符 { } = < >, 再 ; , 再单行注释, 字符串, 词(排除操作符/;)
_TOKEN_RE = re.compile(r'\s+|;|\#[^\n]*|"(?:[^"\\]|\\.)*"|[<>!=]=|[{}=<>]|[^\s{}=<>;\#"]+')
_OPS = {'=', '==', '!=', '<', '<=', '>', '>='}
_INT_RE = re.compile(r'[+-]?\d+$')


class Multi(list):
    """同名键重复 -> 收集成列表。"""
    pass


def _tokens(text):
    for m in _TOKEN_RE.finditer(text):
        s = m.group()
        c = s[0]
        if c in ' \t\r\n' or c == '#' or c == ';':
            continue
        yield s


class _Stream:
    __slots__ = ('_it', '_buf')

    def __init__(self, text):
        self._it = _tokens(text)
        self._buf = None

    def peek(self):
        if self._buf is None:
            self._buf = next(self._it, None)
        return self._buf

    def next(self):
        if self._buf is not None:
            t, self._buf = self._buf, None
            return t
        return next(self._it, None)


def _scalar(t):
    if t is None:
        return None
    if t[0] == '"':
        return t[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    if _INT_RE.match(t):
        return int(t)            # Python 大整数任意精度, 不丢精度
    try:
        return float(t)
    except ValueError:
        return t                 # yes/no / tag / 日期(1444.11.11) 等


def _key(t):
    return t[1:-1] if t and t[0] == '"' else t


def _add(d, k, v):
    if k in d:
        ex = d[k]
        if isinstance(ex, Multi):
            ex.append(v)
        else:
            d[k] = Multi([ex, v])
    else:
        d[k] = v


def _parse_value(s):
    t = s.next()
    if t == '{':
        return _parse_block(s)
    if t in ('rgb', 'hsv', 'hsv360', 'LIST') and s.peek() == '{':
        s.next()
        return _parse_block(s)
    return _scalar(t)


def _parse_block(s):
    """逐元素混合解析: 同时支持 key=value 对、裸列表项、二者混排。
    调用时 '{' 已消费。纯对象->dict; 纯数组->list; 混排->dict 且裸项放 '_items'。"""
    d = {}
    arr = []
    while True:
        p = s.peek()
        if p == '}' or p is None:
            s.next()
            break
        tok = s.next()
        if tok == '{':                       # 裸的嵌套块, 作为数组元素
            arr.append(_parse_block(s))
            continue
        nx = s.peek()
        if nx in _OPS:                       # key <op> value
            s.next()
            _add(d, _key(tok), _parse_value(s))
        elif nx == '{':                      # `key { ... }` 省略了 '='
            s.next()
            _add(d, _key(tok), _parse_block(s))
        else:                                # 裸标量列表项
            arr.append(_scalar(tok))
    if d and arr:
        d['_items'] = arr
        return d
    return d if d else arr


def parse_clausewitz(text):
    if text.startswith('EU4txt'):
        text = text[6:]
    s = _Stream(text)
    d = {}
    while True:
        t = s.peek()
        if t is None:
            break
        if t == '}':            # 顶层多余的右括号, 忽略
            s.next()
            continue
        key = s.next()
        if s.peek() in _OPS:
            s.next()
            _add(d, _key(key), _parse_value(s))
    return d


def load_gamestate_text(path):
    with open(path, 'rb') as f:
        head = f.read(2)
    if head == b'PK':
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            member = 'gamestate' if 'gamestate' in names else names[0]
            raw = z.read(member)
    else:
        with open(path, 'rb') as f:
            raw = f.read()
    if raw[:6] == b'EU4bin':
        raise RuntimeError("铁人/二进制存档(EU4bin)读不了，需先用 rakaly melt 转明文，或关掉铁人模式。")
    return raw.decode('cp1252', errors='replace')


def parse_save(path):
    return parse_clausewitz(load_gamestate_text(path))


# ----------------- 取值工具 -----------------

def gv(d, *keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def items(x):
    """统一成元素列表：重复键(Multi)、数组、单值都摊平成 list。"""
    if x is None:
        return []
    if isinstance(x, list):   # Multi 或普通数组
        return list(x)
    return [x]


def num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def i(x, default=None):
    v = num(x)
    return int(round(v)) if v is not None else default


TAGS = {
    'FRA': '法国', 'ENG': '英格兰', 'GBR': '大不列颠', 'CAS': '卡斯蒂利亚', 'SPA': '西班牙',
    'POR': '葡萄牙', 'ARA': '阿拉贡', 'HAB': '奥地利', 'TUR': '奥斯曼', 'MOS': '莫斯科',
    'RUS': '俄罗斯', 'POL': '波兰', 'PLC': '波兰立陶宛', 'LIT': '立陶宛', 'SWE': '瑞典',
    'DAN': '丹麦', 'NOR': '挪威', 'BRA': '勃兰登堡', 'PRU': '普鲁士', 'SAX': '萨克森',
    'BAV': '巴伐利亚', 'BOH': '波西米亚', 'HUN': '匈牙利', 'MLO': '米兰', 'VEN': '威尼斯',
    'PAP': '教皇国', 'NAP': '那不勒斯', 'SAV': '萨伏依', 'GEN': '热那亚', 'FLO': '佛罗伦萨',
    'TUS': '托斯卡纳', 'NED': '尼德兰', 'BUR': '勃艮第', 'SCO': '苏格兰', 'IRE': '爱尔兰',
    'MAM': '马穆鲁克', 'PER': '波斯', 'TIM': '帖木儿', 'MNG': '明', 'QNG': '清',
    'JAP': '日本', 'KOR': '朝鲜', 'MUG': '莫卧儿', 'DLH': '德里', 'BNG': '孟加拉',
    'VIJ': '维查耶纳伽尔', 'ETH': '埃塞俄比亚', 'MOR': '摩洛哥', 'TUN': '突尼斯',
    'ALG': '阿尔及尔', 'AYU': '阿瑜陀耶', 'GOL': '金帐', 'CRI': '克里米亚',
    'KAZ': '喀山', 'NOV': '诺夫哥罗德', 'TEU': '条顿', 'LIV': '利沃尼亚', 'SER': '塞尔维亚',
}


# ledger 收入/支出表是按索引排的数组 (来自 rakaly/eu4save query.rs)
INCOME_CATS = ['税收', '生产', '贸易', '金币', '关税', '藩属', '港口费', '补贴', '战争赔款',
               '利息', '馈赠', '事件', '战利品', '宝船队', '虹吸', '雇佣金', '知识共享',
               '封锁港口', '劫掠城市', '其他']
EXPENSE_CATS = {0: '顾问维护', 1: '利息', 2: '建省维护', 4: '补贴', 5: '战争赔款', 6: '陆军维护',
                7: '海军维护', 8: '要塞维护', 9: '殖民', 10: '传教', 11: '征兵', 12: '造船',
                13: '建要塞', 14: '建筑', 16: '还贷', 17: '馈赠', 18: '顾问', 19: '事件',
                20: '和平', 21: '藩属费', 22: '关税', 23: '支持效忠', 26: '雇佣兵', 27: '肃贪',
                28: '拥抱制度', 30: '知识共享', 31: '贸易公司投资', 35: '遗迹', 36: '贸易中心升级'}


def _breakdown(table, cats):
    """把 ledger 索引数组拆成 [(类别, 数值)] 按降序; cats 是 list 或 dict。"""
    out = []
    if not isinstance(table, list):
        return out
    for idx, v in enumerate(table):
        val = num(v, 0) or 0
        if val <= 0.001:
            continue
        if isinstance(cats, dict):
            name = cats.get(idx, '其他')
        else:
            name = cats[idx] if idx < len(cats) else '其他'
        out.append([name, round(val, 2)])
    # 同名合并(顾问出现两次等)
    merged = {}
    for n, v in out:
        merged[n] = merged.get(n, 0) + v
    res = [[n, round(v, 2)] for n, v in merged.items()]
    res.sort(key=lambda x: -x[1])
    return res


def tagname(tag):
    if not isinstance(tag, str):
        return str(tag)
    return f"{TAGS[tag]}({tag})" if tag in TAGS else tag


def find_player_tag(top):
    p = gv(top, 'player')
    if isinstance(p, str) and len(p) <= 4:
        return p
    pc = gv(top, 'players_countries')
    if isinstance(pc, (list, Multi)) and len(pc) >= 2:
        return pc[1]
    return None


def extract_state(top):
    """把解析后的存档抽成给前端/给 Claude 用的紧凑状态 dict。"""
    date = gv(top, 'date', default='?')
    year = None
    if isinstance(date, str) and '.' in date:
        try:
            year = int(date.split('.')[0])
        except ValueError:
            pass
    ptag = find_player_tag(top)
    countries = gv(top, 'countries', default={})
    me = countries.get(ptag) if isinstance(countries, dict) else None

    st = {'date': date, 'year': year, 'player_tag': ptag,
          'player_name': tagname(ptag) if ptag else None, 'ok': me is not None}
    if not isinstance(me, dict):
        return st

    powers = gv(me, 'powers')
    if isinstance(powers, (list, Multi)) and len(powers) >= 3:
        st['power'] = {'adm': i(powers[0]), 'dip': i(powers[1]), 'mil': i(powers[2])}

    loans = items(gv(me, 'loan'))
    st['treasury'] = num(gv(me, 'treasury'))
    st['loans'] = len(loans)
    st['debt'] = round(sum(num(gv(l, 'amount'), 0) for l in loans if isinstance(l, dict)))
    st['inflation'] = num(gv(me, 'inflation'))
    st['stability'] = num(gv(me, 'stability'))
    st['prestige'] = num(gv(me, 'prestige'))
    st['legitimacy'] = num(gv(me, 'legitimacy', 'republican_tradition', 'horde_unity', 'devotion', 'meritocracy'))
    st['war_exhaustion'] = num(gv(me, 'war_exhaustion'))
    st['corruption'] = num(gv(me, 'corruption'))

    mp = num(gv(me, 'manpower'))
    st['manpower'] = round(mp * 1000) if mp is not None else None
    mmp = num(gv(me, 'max_manpower'))
    st['max_manpower'] = round(mmp * 1000) if mmp is not None else None

    armies = items(gv(me, 'army'))
    regs = sum(len(items(gv(a, 'regiment'))) for a in armies if isinstance(a, dict))
    if regs == 0:
        regs = i(gv(me, 'num_of_regulars'), 0)
    navies = items(gv(me, 'navy'))
    ships = sum(len(items(gv(n, 'ship'))) for n in navies if isinstance(n, dict))
    st['regiments'] = regs
    st['armies'] = len(armies)
    st['ships'] = ships

    tech = gv(me, 'technology', default={})
    st['tech'] = {'adm': i(gv(tech, 'adm_tech')), 'dip': i(gv(tech, 'dip_tech')), 'mil': i(gv(tech, 'mil_tech'))}

    maxa = maxd = maxm = 0
    devs, gps = [], []   # (tag, value) 用于排名
    if isinstance(countries, dict):
        for tag, c in countries.items():
            if not isinstance(c, dict) or not gv(c, 'num_of_cities'):
                continue
            ct = gv(c, 'technology', default={})
            maxa = max(maxa, i(gv(ct, 'adm_tech'), 0))
            maxd = max(maxd, i(gv(ct, 'dip_tech'), 0))
            maxm = max(maxm, i(gv(ct, 'mil_tech'), 0))
            devs.append((tag, num(gv(c, 'development', 'raw_development'), 0) or 0))
            gps.append((tag, num(gv(c, 'great_power_score'), 0) or 0))
    st['tech_max'] = {'adm': maxa, 'dip': maxd, 'mil': maxm}

    st['development'] = round(num(gv(me, 'development', 'raw_development'), 0))
    st['num_cities'] = i(gv(me, 'num_of_cities'))

    # 排名 (发展度 / 大国分)
    def _rank(pairs):
        order = sorted(pairs, key=lambda x: -x[1])
        for n, (tag, _) in enumerate(order, 1):
            if tag == ptag:
                return n, len(order)
        return None, len(order)
    dev_rank, total = _rank(devs)
    gp_rank, _ = _rank(gps)
    st['rank'] = {'dev_rank': dev_rank, 'total': total, 'gp_rank': gp_rank,
                  'gp_score': round(num(gv(me, 'great_power_score'), 0) or 0),
                  'is_gp': gv(me, 'is_great_power') in ('yes', True, 1)}

    # 财政构成 (ledger 月度收支)
    ledger = gv(me, 'ledger', default={})
    inc_table = gv(ledger, 'lastmonthincometable')
    exp_table = gv(ledger, 'lastmonthexpensetable')
    inc_bd = _breakdown(inc_table, INCOME_CATS)
    exp_bd = _breakdown(exp_table, EXPENSE_CATS)
    monthly_income = num(gv(ledger, 'lastmonthincome'))
    if monthly_income is None and inc_bd:
        monthly_income = sum(v for _, v in inc_bd)
    monthly_expense = sum(v for _, v in exp_bd) if exp_bd else None
    econ = {}
    if monthly_income is not None:
        econ['income'] = round(monthly_income, 2)
    if monthly_expense is not None:
        econ['expense'] = round(monthly_expense, 2)
    if monthly_income is not None and monthly_expense is not None:
        econ['net'] = round(monthly_income - monthly_expense, 2)
    if inc_bd:
        econ['income_top'] = inc_bd[:5]
    if exp_bd:
        econ['expense_top'] = exp_bd[:5]
    st['economy'] = econ

    # 其它直接字段
    st['absolutism'] = num(gv(me, 'absolutism'))
    st['mercantilism'] = num(gv(me, 'mercantilism'))
    st['army_tradition'] = num(gv(me, 'army_tradition'))
    st['navy_tradition'] = num(gv(me, 'navy_tradition'))
    st['power_projection'] = num(gv(me, 'current_power_projection'))
    sail = num(gv(me, 'sailors'))
    st['sailors'] = round(sail) if sail is not None else None
    msail = num(gv(me, 'max_sailors'))
    st['max_sailors'] = round(msail) if msail is not None else None
    subs = gv(me, 'subjects')
    st['subjects'] = [tagname(t) for t in items(subs)] if subs else []
    st['enemies'] = [tagname(t) for t in items(gv(me, 'enemy')) if isinstance(t, str)]

    ideas = gv(me, 'active_idea_groups')
    st['ideas'] = dict(ideas) if isinstance(ideas, dict) else {}

    st['religion'] = gv(me, 'religion', 'dominant_religion')
    gov = gv(me, 'government')
    st['government'] = gv(gov, 'government') if isinstance(gov, dict) else gov
    st['government_rank'] = i(gv(me, 'government_rank'))

    # 外交
    dip = gv(top, 'diplomacy', default={})
    allies = []
    for al in items(gv(dip, 'alliance')):
        if isinstance(al, dict):
            f, s = gv(al, 'first'), gv(al, 'second')
            if ptag in (f, s):
                allies.append(s if f == ptag else f)
    st['allies'] = [tagname(t) for t in allies]

    st['my_rivals'] = [tagname(gv(r, 'country', default=r) if isinstance(r, dict) else r)
                       for r in items(gv(me, 'rival')) if r]
    rivals_me, coalition = [], []
    if isinstance(countries, dict):
        for tag, c in countries.items():
            if tag == ptag or not isinstance(c, dict):
                continue
            for r in items(gv(c, 'rival')):
                rt = gv(r, 'country', default=r) if isinstance(r, dict) else r
                if rt == ptag:
                    rivals_me.append(tag)
                    break
            if gv(c, 'coalition_target') == ptag:
                coalition.append(tag)
    st['rivals_me'] = [tagname(t) for t in rivals_me]
    st['coalition'] = [tagname(t) for t in coalition]

    # 战争
    wars = []
    for w in items(gv(top, 'active_war')):
        if not isinstance(w, dict):
            continue
        att = [x for x in items(gv(w, 'attacker')) if isinstance(x, str)]
        dfn = [x for x in items(gv(w, 'defender')) if isinstance(x, str)]
        if not att and not dfn:
            parts = [gv(p, 'tag') for p in items(gv(w, 'participants')) if isinstance(p, dict)]
            if ptag in parts:
                wars.append({'name': gv(w, 'name', default='战争'),
                             'mine': [tagname(t) for t in parts], 'enemy': []})
            continue
        if ptag in att or ptag in dfn:
            mine = att if ptag in att else dfn
            enemy = dfn if ptag in att else att
            wars.append({'name': gv(w, 'name', default='战争'),
                         'mine': [tagname(t) for t in mine], 'enemy': [tagname(t) for t in enemy]})
    st['wars'] = wars
    return st


# ----------------- 找存档 -----------------

def default_dirs():
    home = os.path.expanduser("~")
    base = os.path.join("Paradox Interactive", "Europa Universalis IV", "save games")
    return [os.path.join(home, d, base) for d in
            ("Documents", os.path.join("OneDrive", "Documents"),
             os.path.join("OneDrive", "ドキュメント"), "ドキュメント")]


def find_dir(arg_dir=None):
    if arg_dir and os.path.isdir(arg_dir):
        return arg_dir
    for d in default_dirs():
        if os.path.isdir(d):
            return d
    return None


def latest_save(d):
    if not d or not os.path.isdir(d):
        return None
    saves = glob.glob(os.path.join(d, "*.eu4"))
    return max(saves, key=os.path.getmtime) if saves else None


if __name__ == "__main__":
    args = sys.argv[1:]
    keys = '--keys' in args
    args = [a for a in args if not a.startswith('--')]
    path = args[0] if args else latest_save(find_dir())
    if not path:
        print("没找到存档，把 .eu4 路径当参数传进来。")
        sys.exit(1)
    top = parse_save(path)
    if keys:
        ptag = find_player_tag(top)
        me = gv(top, 'countries', default={}).get(ptag)
        print("玩家 tag:", ptag)
        print("顶层字段:", ", ".join(sorted(top.keys())))
        if isinstance(me, dict):
            print("玩家国字段:", ", ".join(sorted(me.keys())))
            print("technology:", gv(me, 'technology'))
    else:
        print(json.dumps(extract_state(top), ensure_ascii=False, indent=2))
