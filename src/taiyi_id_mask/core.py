"""個資偵測、遮蔽、還原與送出前檢查。

三層做法，任何一層都可以單獨用：

1. 欄位白名單 `minimize_record()`：結構化資料只留需要的欄位；出生日期換成年齡層。
2. 文字遮蔽 `mask()`：自由文字裡的個資換成代號，例如「[姓名1]」；同一個原值用同一個代號。
3. 送出前檢查 `guard()`：遮蔽後再掃一次，還有可疑內容就丟 `PIIBlocked`（寧可不送）。

代號與原值的對照表（`MaskResult.mapping`）只能留在本機。

格式依據：
- 國民身分證統一編號、新式外來人口統一證號：1 碼英文字母加 9 碼數字；舊式居留證統一證號：2 碼英文字母加 8 碼數字。
  新式統一證號自 110 年 1 月 2 日起與國民身分證同格式（內政部移民署說明）。
  本套件只比對格式、不驗檢查碼：寧可多遮，不漏遮。
- 縣市與鄉鎮市區名稱：`data/tw_place_names.json`，出處見該檔 attribution 欄位與 NOTICE。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple, Union

_DATA = Path(__file__).resolve().parent / 'data' / 'tw_place_names.json'
_places = json.loads(_DATA.read_text(encoding='utf-8'))
COUNTIES = set(_places['counties']) | {c.replace('臺', '台') for c in _places['counties']}
TOWNS = set(_places['towns'])

CJK = '[一-鿿]'
NUM = '[0-9０-９一二三四五六七八九十百]+'

#: 內建偵測項目：(類別, 正規表示式)。
PATTERNS: List[Tuple[str, Pattern]] = [
    ('電子郵件', re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')),
    ('身分證號', re.compile(r'(?<![A-Za-z0-9])[A-Za-z][0-9]{9}(?![0-9])')),
    ('身分證號', re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Da-d][0-9]{8}(?![0-9])')),
    ('電話', re.compile(r'(?<![0-9])(?:\+?886[-\s]?|0)9[0-9]{2}[-\s]?[0-9]{3}[-\s]?[0-9]{3}(?![0-9])')),
    ('電話', re.compile(r'(?<![0-9])(?:\(0[2-8][0-9]{0,2}\)|0[2-8][0-9]{0,2})[-\s]?[0-9]{3,4}[-\s]?[0-9]{3,4}'
                      r'(?:[#分機轉]+[0-9]{1,5})?(?![0-9])')),
    ('日期', re.compile(r'(?<![0-9])(?:19|20)[0-9]{2}[-/.年](?:0?[1-9]|1[0-2])[-/.月](?:0?[1-9]|[12][0-9]|3[01])日?(?![0-9])')),
    ('日期', re.compile(r'(?:民國)?(?<![0-9])[0-9]{2,3}[-/.年](?:0?[1-9]|1[0-2])[-/.月](?:0?[1-9]|[12][0-9]|3[01])日?(?![0-9])')),
    ('長串數字', re.compile(r'(?<![0-9])[0-9]{8,}(?![0-9])')),
]

_place_alt = '|'.join(sorted((re.escape(x) for x in COUNTIES | TOWNS), key=len, reverse=True))
#: 地址：縣市或鄉鎮開頭，後面接村里、鄰、路街（段）、巷、弄、號、樓；各段可省略，但至少要有一段。
ADDRESS = re.compile(
    rf'(?:{_place_alt})+'
    rf'(?:{CJK}{{1,4}}?[村里])?(?:{NUM}鄰)?'
    rf'(?:{CJK}{{1,6}}?(?:路|街|大道)(?:{NUM}段)?)?'
    rf'(?:{NUM}巷)?(?:{NUM}弄)?(?:{NUM}(?:之{NUM})?號)?(?:{NUM}樓(?:之{NUM})?)?')
_ADDRESS_PART = re.compile('[村里鄰路街道巷弄號樓]')
_PLACE_PREFIX = re.compile(rf'(?:{_place_alt})+')

# 稱謂前的人名：1～3 個中文字，遇到「說、的、這位」這類虛字就斷開，避免把前一句吃進來
_NAME_CHAR = '(?:(?![說的是和跟與位這那給向對請叫及或在有了到找問])[一-鿿])'
# 「家屬王先生」「病人陳小姐」：前面的身分詞不算名字
_ROLE = '(?:家屬|病人|個案|患者|案主|聯絡人|看護|鄰居|同事|朋友)'
HONORIFIC = re.compile(rf'{_ROLE}?({_NAME_CHAR}{{1,3}})(?=先生|小姐|女士|太太|阿嬤|阿公|伯伯|阿姨|媽媽|爸爸)')
# 「家屬：女兒陳美玲」：標籤後面的稱謂詞跳過，只取人名
KIN = '(?:女兒|兒子|媳婦|女婿|太太|先生|丈夫|妻子|配偶|母親|父親|媽媽|爸爸|孫子|孫女|弟弟|妹妹|哥哥|姊姊|姐姐|看護)'
LABELED_NAME = re.compile(rf'(?:姓名|病人|個案|患者|家屬|聯絡人)\s*[:：]\s*{KIN}?(?!{KIN})({CJK}{{2,4}})')
LABELED_ANY = re.compile(r'(?:身分證|身份證|統一證號|病歷號|健保卡|地址|住址|電話|手機|生日|出生)(?:字號|號碼|號)?'
                         r'\s*[:：]\s*([^\s，,。；;]{2,40})')
_TOKEN = re.compile(r'\[[^\[\]]+\d+\]')
# 換回時也認得全形括號（［姓名1］、【姓名1】）和括號內的空白：別人或其他程式改寫回覆時常這樣
_ANY_TOKEN = re.compile(r'[\[［【]\s*([^\[\]［］【】\s]+?\d+)\s*[\]］】]')

Known = Optional[Dict[str, Union[str, Iterable[str]]]]
Extra = Optional[Iterable[Tuple[str, Union[str, Pattern]]]]


@dataclass
class Finding:
    """一處疑似個資：類別、起訖位置、原文。"""
    kind: str
    start: int
    end: int
    value: str


@dataclass
class MaskResult:
    """遮蔽結果。mapping 是代號 → 原值，只能留在本機。"""
    text: str
    findings: List[Finding]
    mapping: Dict[str, str] = field(default_factory=dict)


class PIIBlocked(Exception):
    """遮蔽後仍偵測到個資，呼叫端不得送出。"""

    def __init__(self, residual: List[Finding]):
        self.residual = residual
        super().__init__('遮蔽後仍有疑似個資：' + '、'.join(f'{f.kind}「{f.value}」' for f in residual))


def _known_items(known: Known) -> List[Tuple[str, str]]:
    items = []
    for kind, values in (known or {}).items():
        if isinstance(values, str):
            values = [values]
        for v in values or []:
            v = str(v).strip()
            if len(v) >= 2:
                items.append((kind, v))
            # 三字以上的姓名，文字裡常只寫名字（「大明說…」），名字也一起遮
            if kind == '姓名' and len(v) >= 3:
                items.append((kind, v[1:]))
    return sorted(items, key=lambda x: len(x[1]), reverse=True)


def _compile_extra(extra: Extra) -> List[Tuple[str, Pattern]]:
    return [(k, p if hasattr(p, 'finditer') else re.compile(p)) for k, p in (extra or [])]


def scan(text: str, known: Known = None, extra: Extra = None) -> List[Finding]:
    """找出文字裡的疑似個資，回傳不重疊的位置（長的優先）。

    known：已知值，例如 {'姓名': ['王大明'], '電話': '0912345678'}，原樣出現就算。
    extra：額外的 (類別, 正規表示式)，例如醫院自己的病歷號格式。
    """
    # 已知值最可靠，先佔位置；其他規則只能填在已知值以外的地方
    first: List[Finding] = []
    for kind, v in _known_items(known):
        for m in re.finditer(re.escape(v), text):
            first.append(Finding(kind, m.start(), m.end(), v))
    cands: List[Finding] = []
    for m in LABELED_NAME.finditer(text):
        cands.append(Finding('姓名', m.start(1), m.end(1), m.group(1)))
    for m in LABELED_ANY.finditer(text):
        cands.append(Finding('標籤個資', m.start(1), m.end(1), m.group(1)))
    for kind, pat in _compile_extra(extra) + PATTERNS:
        for m in pat.finditer(text):
            cands.append(Finding(kind, m.start(), m.end(), m.group(0)))
    for m in ADDRESS.finditer(text):
        if _ADDRESS_PART.search(m.group(0)[_PLACE_PREFIX.match(m.group(0)).end():]):
            cands.append(Finding('地址', m.start(), m.end(), m.group(0)))
    for m in HONORIFIC.finditer(text):
        cands.append(Finding('姓名', m.start(1), m.end(1), m.group(1)))
    first.sort(key=lambda f: (-(f.end - f.start), f.start))
    cands.sort(key=lambda f: (-(f.end - f.start), f.start))
    taken: List[Finding] = []
    for f in first + cands:
        if all(f.end <= t.start or f.start >= t.end for t in taken):
            taken.append(f)
    return sorted(taken, key=lambda f: f.start)


def mask(text: str, known: Known = None, extra: Extra = None) -> MaskResult:
    """把疑似個資換成代號；同一個原值用同一個代號。"""
    findings = scan(text, known, extra)
    mapping: Dict[str, str] = {}
    reverse: Dict[Tuple[str, str], str] = {}
    counter: Dict[str, int] = {}
    out, pos = [], 0
    for f in findings:
        key = (f.kind, f.value)
        if key not in reverse:
            counter[f.kind] = counter.get(f.kind, 0) + 1
            token = f'[{f.kind}{counter[f.kind]}]'
            reverse[key] = token
            mapping[token] = f.value
        out.append(text[pos:f.start])
        out.append(reverse[key])
        pos = f.end
    out.append(text[pos:])
    return MaskResult(''.join(out), findings, mapping)


def unmask(text: str, mapping: Dict[str, str]) -> str:
    """把回覆裡的代號換回原值（只在本機做）。對照表裡沒有的代號原樣保留。"""
    text = _ANY_TOKEN.sub(lambda m: mapping.get('[' + m.group(1) + ']', m.group(0)), text)
    # 不是 [類別數字] 形式的自訂代號，照原樣逐字換
    for token, value in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
        if not _TOKEN.fullmatch(token):
            text = text.replace(token, value)
    return text


def guard(text: str, known: Known = None, extra: Extra = None) -> MaskResult:
    """遮蔽後再掃一次；還有殘留就丟 PIIBlocked。"""
    result = mask(text, known, extra)
    residual = [f for f in scan(result.text, known, extra) if not _TOKEN.fullmatch(f.value)]
    if residual:
        raise PIIBlocked(residual)
    return result


def age_band(birth: date, today: Optional[date] = None, width: int = 5) -> str:
    """出生日期換成年齡層，例如「65-69 歲」；90 歲以上合併成一組。"""
    today = today or date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if age >= 90:
        return '90 歲以上'
    lo = age // width * width
    return f'{lo}-{lo + width - 1} 歲'


def minimize_record(record: dict, allowed: Iterable[str], today: Optional[date] = None,
                    birth_field: str = 'birth_date') -> dict:
    """結構化資料只留白名單欄位；allowed 含 'age_band' 時，出生日期換成年齡層，不送原始日期。"""
    allowed = list(allowed)
    out = {k: record[k] for k in allowed if k in record and k != birth_field}
    if birth_field in record and 'age_band' in allowed:
        b = record[birth_field]
        b = date.fromisoformat(b) if isinstance(b, str) else b
        out['age_band'] = age_band(b, today)
    return out
