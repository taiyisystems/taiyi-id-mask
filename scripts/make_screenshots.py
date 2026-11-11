"""產生 README 用的畫面截圖 docs/images/*.png（用範例的虛構資料）。

執行：python scripts/make_screenshots.py
需要本機有 Microsoft Edge 或 Google Chrome（用無頭模式截圖，不會開出視窗）。
做法：複製一份 個資馬賽克.html，最後加一段操作（按「用範例試試看」、切到第二頁等），再截圖。
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'images'
SIZE = (1280, 760)

SCENES = {
    # 檔名：在頁面上做的操作
    'mask.png': "$('sample').click();",
    'restore.png': "$('sample').click(); $('tab-restore').click(); $('trymasked').click();",
    'dark.png': "theme('dark'); $('sample').click();",
}
SCRIPT = """<script>
(function () {
  var $ = function (id) { return document.getElementById(id); };
  // 配色記在瀏覽器，頁面載入完會再套一次；每張圖先記好自己的配色
  function theme(t) { try { localStorage.setItem('taiyi-id-mask-theme', t); } catch (e) {} }
  theme('light');
  %s
  document.activeElement && document.activeElement.blur();
})();
</script>
</body>"""


def browser():
    for p in [os.environ.get('BROWSER_EXE', ''),
              r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              shutil.which('msedge') or '', shutil.which('google-chrome') or '', shutil.which('chromium') or '']:
        if p and Path(p).exists():
            return p
    sys.exit('找不到 Edge 或 Chrome；可用環境變數 BROWSER_EXE 指定瀏覽器路徑')


def main():
    html = (ROOT / '個資馬賽克.html').read_text(encoding='utf-8')
    assert html.count('</body>') == 1
    OUT.mkdir(parents=True, exist_ok=True)
    exe = browser()
    with tempfile.TemporaryDirectory() as tmp:
        for name, actions in SCENES.items():
            page = Path(tmp) / (Path(name).stem + '.html')
            page.write_text(html.replace('</body>', SCRIPT % actions), encoding='utf-8')
            target = OUT / name
            subprocess.run([exe, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
                            f'--user-data-dir={Path(tmp) / "profile"}', '--force-device-scale-factor=2',
                            f'--window-size={SIZE[0]},{SIZE[1]}', '--virtual-time-budget=3000',
                            f'--screenshot={target}', page.as_uri()],
                           check=True, capture_output=True, timeout=120)
            print(target.relative_to(ROOT), target.stat().st_size)


if __name__ == '__main__':
    main()
