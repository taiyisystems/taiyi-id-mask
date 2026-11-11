"""從內政部國土測繪中心「鄉鎮市區界線(TWD97經緯度)」原始 zip 重建 data/tw_place_names.json。

資料集頁面：https://data.gov.tw/dataset/7441
用法：python scripts/build_place_names.py TOWN_MOI_1140318.zip
只讀 zip 內 TOWN_MOI_*.dbf 的 COUNTYNAME、TOWNNAME 兩欄（標準函式庫，不需要 GIS 套件）。
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'src' / 'taiyi_id_mask' / 'data' / 'tw_place_names.json'


def read_dbf(raw: bytes, encoding: str):
    nrec = int.from_bytes(raw[4:8], 'little')
    hlen = int.from_bytes(raw[8:10], 'little')
    rlen = int.from_bytes(raw[10:12], 'little')
    fields, p = [], 32
    while raw[p] != 0x0D:
        fields.append((raw[p:p + 11].split(b'\0')[0].decode('ascii'), raw[p + 16]))
        p += 32
    for i in range(nrec):
        rec = raw[hlen + i * rlen: hlen + (i + 1) * rlen]
        if rec[:1] == b'*':  # 已刪除的紀錄
            continue
        row, off = {}, 1
        for name, size in fields:
            row[name] = rec[off:off + size].decode(encoding).strip()
            off += size
        yield row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('zip')
    a = ap.parse_args()
    zpath = Path(a.zip)
    z = zipfile.ZipFile(zpath)
    names = z.namelist()
    dbf = next(n for n in names if re.fullmatch(r'TOWN_MOI_\d+\.dbf', n, re.I))
    cpg = dbf[:-4] + '.CPG'
    enc = z.read(cpg).decode('ascii').strip() if cpg in names else 'utf-8'
    enc = {'UTF-8': 'utf-8', '65001': 'utf-8'}.get(enc.upper(), enc)
    rows = list(read_dbf(z.read(dbf), enc))
    version = re.search(r'(\d{7})', dbf).group(1)
    out = {
        'attribution': f'資料來源：內政部國土測繪中心「鄉鎮市區界線(TWD97經緯度)」{version} 版（https://data.gov.tw/dataset/7441）',
        'license_statement': '此開放資料依政府資料開放授權條款 (Open Government Data License) 進行公眾釋出，'
                             '使用者於遵守本條款各項規定之前提下，得利用之。政府資料開放授權條款：https://data.gov.tw/license',
        'source_file': zpath.name,
        'source_sha256': hashlib.sha256(zpath.read_bytes()).hexdigest(),
        'counties': sorted({r['COUNTYNAME'] for r in rows}),
        'towns': sorted({r['TOWNNAME'] for r in rows}),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(rows)} 筆紀錄 → 縣市 {len(out["counties"])}、鄉鎮市區名稱 {len(out["towns"])}：{OUT}')


if __name__ == '__main__':
    main()
