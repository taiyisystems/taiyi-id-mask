"""命令列：taiyi-id-mask 檔案 [--known 已知值.json] [--strict] [--json]"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import PIIBlocked, guard, mask


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='taiyi-id-mask', description='偵測並遮蔽文字檔裡的個資（UTF-8）。')
    ap.add_argument('file', help='要檢查的文字檔；用 - 代表標準輸入')
    ap.add_argument('--known', help='JSON 檔：{"姓名": ["王大明"], "電話": ["0912345678"]}')
    ap.add_argument('--strict', action='store_true', help='遮蔽後仍有殘留就以代碼 2 結束，不輸出內容')
    ap.add_argument('--json', action='store_true', help='輸出 JSON（含偵測位置；不含代號對照表）')
    ap.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    a = ap.parse_args(argv)
    text = sys.stdin.read() if a.file == '-' else Path(a.file).read_text(encoding='utf-8')
    known = json.loads(Path(a.known).read_text(encoding='utf-8')) if a.known else None
    try:
        r = guard(text, known) if a.strict else mask(text, known)
    except PIIBlocked as e:
        print(e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({'text': r.text, 'findings': [{'kind': f.kind, 'start': f.start, 'end': f.end}
                                                        for f in r.findings]}, ensure_ascii=False))
    else:
        print(r.text)
        kinds = '、'.join(sorted({f.kind for f in r.findings})) or '無'
        print(f'# 遮蔽 {len(r.findings)} 處：{kinds}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
