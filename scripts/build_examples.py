"""產生 examples/ 的範例檔（全部是虛構資料），給使用者拖進網頁版試用。

執行：python scripts/build_examples.py
只用標準函式庫：Word、Excel 檔是照 Office Open XML 格式直接寫出最小的檔案。
"""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'examples'
STAMP = (2026, 11, 11, 0, 0, 0)  # 固定時間，重跑產生的檔案位元組不變

REFERRAL = [
    '衛生所個案轉介單（虛構資料，範例用）',
    '',
    '個案姓名：陳志明　性別：男　出生：民國45年8月20日',
    '身分證字號：E123456789',
    '聯絡電話：07-3123456　手機 0933-111-222',
    '住址：高雄市三民區建國二路3號5樓',
    '轉介原因：志明最近血壓控制不佳，收縮壓 168 mmHg，糖化血色素 HbA1c 8.1%。',
    '家屬：女兒陳美玲（0955-222-333），陳小姐表示可陪同就醫。',
    '承辦人：衛生所護理師',
]
TABLE = [
    ['編號', '姓名', '身分證號', '手機', '地址', '收縮壓', '備註'],
    ['1', '王大明', 'A123456789', '0912-345-678', '臺北市大安區信義路四段1號', '142', '王先生說會準時回診'],
    ['2', '林美華', 'T223456789', '0922-333-444', '屏東縣屏東市自由路272號3樓', '162', '獨居，需家訪'],
    ['3', '張雅婷', 'F234567890', '0988-765-432', '新北市板橋區文化路一段100號', '118', '已完成衛教'],
]
VISIT = '''居家訪視紀錄（虛構資料，範例用）

訪視日期：2026-10-28
個案姓名：黃淑芬，身分證 B223344556，住臺中市北區三民路三段129號。
個案自述最近睡不好，空腹血糖 135 mg/dL，血壓 140/90。
兒子黃建國（0911-222-333）表示每週三會回家探視，聯絡信箱 jianguo.huang@example.com。
下次訪視：2026-11-25，請先以電話 04-22223333 聯絡。
'''
OLD_LETTER = '''來文單位：某某衛生局（虛構資料，範例用）
主旨：請協助追蹤個案李大同先生（身分證 F123456789）。
說明：個案住花蓮縣秀林鄉富世村5鄰，電話 03-8612345，1990/05/17 出生。
'''
# 「② 把代號換回真名」用：先在 ① 遮好「轉介單.docx」，再把這段拖進 ②
REPLY = '''[姓名1] 先生您好：

您最近的收縮壓 168 mmHg、HbA1c 8.1%，都比目標高，請於下週三上午回衛生所複診。
當天可請家屬 [姓名3] 陪同。若時間不方便，請撥 [電話1] 與護理師改約。
'''


def write_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


def docx(path, paragraphs):
    body = ''.join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
    write_zip(path, [
        ('[Content_Types].xml',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
        ('_rels/.rels',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" '
         'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
         'Target="word/document.xml"/></Relationships>'),
        ('word/document.xml',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
         f'<w:body>{body}</w:body></w:document>'),
    ])


def col(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx(path, rows):
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = ''.join(f'<c r="{col(c)}{r}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for c, v in enumerate(row))
        xml_rows.append(f'<row r="{r}">{cells}</row>')
    write_zip(path, [
        ('[Content_Types].xml',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/xl/workbook.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
         '<Override PartName="/xl/worksheets/sheet1.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'),
        ('_rels/.rels',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" '
         'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
         'Target="xl/workbook.xml"/></Relationships>'),
        ('xl/workbook.xml',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
         '<sheets><sheet name="個案名單" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        ('xl/_rels/workbook.xml.rels',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" '
         'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
         'Target="worksheets/sheet1.xml"/></Relationships>'),
        ('xl/worksheets/sheet1.xml',
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
         f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'),
    ])


def csv_text(rows):
    def cell(v):
        return '"' + v.replace('"', '""') + '"' if any(c in v for c in ',"\r\n') else v
    return '\r\n'.join(','.join(cell(v) for v in row) for row in rows) + '\r\n'


def main():
    OUT.mkdir(exist_ok=True)
    docx(OUT / '轉介單.docx', REFERRAL)
    xlsx(OUT / '個案名單.xlsx', TABLE)
    # CSV 加 BOM，Excel 直接開才不會亂碼
    (OUT / '個案名單.csv').write_bytes(b'\xef\xbb\xbf' + csv_text(TABLE).encode('utf-8'))
    (OUT / '訪視紀錄.txt').write_bytes(VISIT.replace('\n', '\r\n').encode('utf-8'))
    (OUT / '舊公文-Big5.txt').write_bytes(OLD_LETTER.replace('\n', '\r\n').encode('big5'))
    (OUT / '回覆範例-換回真名用.txt').write_bytes(REPLY.replace('\n', '\r\n').encode('utf-8'))
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size)


if __name__ == '__main__':
    main()
