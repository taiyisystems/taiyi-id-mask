"""組出給一般使用者下載的整包 dist/taiyi-id-mask-web.zip（GitHub Releases 與線上試用網站都放這一包）。

執行：python scripts/build_release.py
內容：解壓後只有一個資料夾「個資馬賽克」，裡面是網頁本身、使用說明、範例檔，雙擊網頁就能用。
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
NAME = 'taiyi-id-mask-web.zip'
TOP = '個資馬賽克'
STAMP = (2026, 1, 1, 0, 0, 0)  # 固定時間，同一版內容重跑產生的 zip 相同

GUIDE = '''個資馬賽克 {version}（taiyi-id-mask）
================================

把文字裡的姓名、身分證號、電話、地址遮起來。全部在這台電腦處理，不會上網，資料不會傳出去。

怎麼用
------
1. 雙擊「個資馬賽克.html」，會用 Edge 或 Chrome 打開。不用安裝。
2. 把文字貼進左邊框框，或把 Word、Excel、文字檔拖進去。
3. 右邊自動出現遮好的結果，按「複製結果」，貼到要用的地方。

第一次用可以按「用範例試試看」，或把「範例檔案」資料夾裡的檔案拖進去（全部是虛構資料）。

把代號換回真名
--------------
遮好的文字交給 AI 或廠商處理，拿回來的文字還有 [姓名1] 這種代號時，
到網頁上方「② 把代號換回真名」，貼上或把檔案拖進去，就會換回真名。
隔天以後才要換的，先在 ① 按「存對照表」。對照表裡有真實個資，只能留在自己電腦，不要寄出去。

注意
----
這是輔助工具：沒有稱謂、沒有標籤、也沒填在「這份資料裡有誰的名字」的人名可能抓不到，
送出前請再看一眼。

線上試用：https://taiyisystems.github.io/taiyi-id-mask/
專案網頁：https://github.com/taiyisystems/taiyi-id-mask
開源專案創建與維護：台醫資訊　授權：Apache-2.0
'''


def main():
    init = (ROOT / 'src' / 'taiyi_id_mask' / '__init__.py').read_text(encoding='utf-8')
    version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", init).group(1)
    files = [(ROOT / '個資馬賽克.html', '個資馬賽克.html'), (ROOT / 'LICENSE', 'LICENSE.txt'), (ROOT / 'NOTICE', 'NOTICE.txt')]
    for p in sorted((ROOT / 'examples').iterdir()):
        if p.suffix.lower() in ('.docx', '.xlsx', '.csv', '.txt'):
            files.append((p, '範例檔案/' + p.name))
    DIST.mkdir(exist_ok=True)
    out = DIST / NAME
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        # 記事本直接開也不會亂碼：UTF-8 加 BOM、Windows 換行
        guide = '﻿' + GUIDE.format(version=version).replace('\n', '\r\n')
        z.writestr(zipfile.ZipInfo(f'{TOP}/使用說明.txt', STAMP), guide.encode('utf-8'), zipfile.ZIP_DEFLATED)
        for src, arc in files:
            info = zipfile.ZipInfo(f'{TOP}/{arc}', STAMP)
            z.writestr(info, src.read_bytes(), zipfile.ZIP_DEFLATED)
    # GitHub Release 的說明：下載方式＋更新紀錄裡這一版的內容
    log = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(r'^## ' + re.escape(version) + r' .*?\n(.*?)(?=^## |\Z)', log, re.S | re.M)
    notes = ('**下載：** 下面的 `taiyi-id-mask-web.zip`，解壓後雙擊「個資馬賽克.html」就能用，不用安裝。\n\n'
             '**線上試用：** https://taiyisystems.github.io/taiyi-id-mask/\n\n' + (m.group(1).strip() if m else ''))
    (DIST / 'release-notes.md').write_text(notes + '\n', encoding='utf-8')
    print(out.relative_to(ROOT), out.stat().st_size, file=sys.stderr)


if __name__ == '__main__':
    main()
