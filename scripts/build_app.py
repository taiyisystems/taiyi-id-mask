"""把離線網頁組成單一檔案：app/app.html + app/engine.js + 地名表 → 個資馬賽克.html

執行：python scripts/build_app.py
改了 app/ 或地名表之後要重跑；tests/test_app.py 會檢查成品是不是最新的。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '個資馬賽克.html'


def build() -> str:
    html = (ROOT / 'app' / 'app.html').read_text(encoding='utf-8')
    engine = (ROOT / 'app' / 'engine.js').read_text(encoding='utf-8')
    places = json.loads((ROOT / 'src' / 'taiyi_id_mask' / 'data' / 'tw_place_names.json').read_text(encoding='utf-8'))
    init = (ROOT / 'src' / 'taiyi_id_mask' / '__init__.py').read_text(encoding='utf-8')
    version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", init).group(1)
    data = {'counties': places['counties'], 'towns': places['towns']}
    places_js = ('// 縣市與鄉鎮市區名稱：' + places['attribution'] + '\n'
                 'var PLACES = ' + json.dumps(data, ensure_ascii=False) + ';')
    return (html.replace('/*__PLACES__*/', places_js)
                .replace('/*__ENGINE__*/', engine)
                .replace('/*__VERSION__*/', version))


if __name__ == '__main__':
    OUT.write_text(build(), encoding='utf-8', newline='\n')
    print(f'已產生 {OUT.name}', file=sys.stderr)
