# -*- coding: utf-8 -*-
"""EU4 普通局存档解析 + 状态抽取 (零第三方依赖)。
被 server.py 调用; 也能单独 `python eu4_parser.py <save> --keys` 调试字段名。
铁人(EU4bin)存档读不了, 需先 rakaly melt。
"""
import sys, os, re, zipfile, glob, json

_TOKEN_RE = re.compile(r'\s+|\#[^\n]*|"(?:[^"\\]|\\.)*"|[{}=]|[^\s{}=\#"]+')


class Multi(list):
    pass


def _tokens(text):
    for m in _TOKEN_RE.finditer(text):
        s = m.group()
        c = s[0]
        if c in ' \t\r\n' or c == '#':
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
        return t[1:-1].replace('\\"', '"')
    try:
        if '.' not in t and 'e' not in t and 'E' not in t:
            return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return t


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
    if t in ('rgb', 'hsv', 'hsv360') and s.peek() == '{':
        s.next()
        return _parse_block(s)
    return _scalar(t)


def _parse_block(s):
    first = s.peek()
    if first == '}' or first is None:
        s.next()
        return {}
    t1 = s.next()
    if s.peek() == '=':
        d = {}
        s.next()
        _add(d, t1, _parse_value(s))
        while True:
            p = s.peek()
            if p == '}' or p is None:
                s.next()
                break
            key = s.next()
            if s.next() != '=':
                continue
            _add(d, key, _parse_value(s))
        return d
    else:
        arr = [_parse_block(s) if t1 == '{' else _scalar(t1)]
        while True:
            p = s.peek()
            if p == '}' or p is None:
                s.next()
                break
            arr.append(_parse_value(s))
        return arr


def parse_clausewitz(text):
    if text.startswith('EU4txt'):
        text = text[6:]
    s = _Stream(text)
    d = {}
    while True:
        if s.peek() is None:
            break
        key = s.next()
        if s.peek() == '=':
            s.next()
            _add(d, key, _parse_value(s))
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
    if isinstance(countries, dict):
        for tag, c in countries.items():
            if not isinstance(c, dict) or not gv(c, 'num_of_cities'):
                continue
            ct = gv(c, 'technology', default={})
            maxa = max(maxa, i(gv(ct, 'adm_tech'), 0))
            maxd = max(maxd, i(gv(ct, 'dip_tech'), 0))
            maxm = max(maxm, i(gv(ct, 'mil_tech'), 0))
    st['tech_max'] = {'adm': maxa, 'dip': maxd, 'mil': maxm}

    st['development'] = round(num(gv(me, 'development', 'raw_development'), 0))
    st['num_cities'] = i(gv(me, 'num_of_cities'))

    ideas = gv(me, 'active_idea_groups')
    st['ideas'] = dict(ideas) if isinstance(ideas, dict) else {}

    st['religion'] = gv(me, 'religion')
    st['government'] = gv(me, 'government')

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
