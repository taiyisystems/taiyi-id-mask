"""離線網頁（個資馬賽克.html）的檢查：JavaScript 偵測結果要和 Python 版完全一樣，成品要是最新的。

需要 Node.js；沒有就跳過比對。測試資料都是虛構的。
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import taiyi_id_mask as idmask  # noqa: E402
import build_app  # noqa: E402

KNOWN = {'姓名': ['林美華', '王大明'], '電話': ['0912-345-678'], '指定': ['PT-12345']}
CASES = [
    '身分證 A123456789 已核對', '新式統一證號 A800000014', '舊式居留證 AC01234567',
    '手機0912345678', '手機：0912345678', '請撥 0912-345-678 聯絡', '衛生所 08-7370002 分機121',
    '+886 912 345 678', '(02)2345-6789', '寄到 abc.def@example.com',
    '1958/03/12 出生', '民國47年3月12日', '115.11.06 回診', '2026-11-06',
    '住在屏東縣屏東市自由路272號3樓，獨居', '台中市北區三民路三段129號', '花蓮縣秀林鄉富世村5鄰',
    '臺北市大安區信義路四段1之2號5樓之3', '屏東縣衛生局轉介', '高雄市三民區',
    '姓名：陳小明，男', '王先生主訴胸悶', '美華說最近頭暈', '他跟陳小姐說的那位張太太',
    '收縮壓 162 mmHg，舒張壓 98，空腹血糖 135 mg/dL，HbA1c 7.2%，BMI 29.4，血壓 140/90，eGFR 48',
    '編號0012345678', '病歷號：A0012345', '病歷 PT-12345 已建檔', '地址：屏東市自由路272號，電話：08-7654321',
    '王先生說王先生昨天沒吃藥', '家屬王先生表示', '病人陳大明先生', '家屬：女兒陳美玲', '家屬：女兒王大明，大明表示可陪同',
    '個案姓名：林美華，身分證 T223456789，民國47年3月12日生。\n住屏東縣屏東市自由路272號3樓，手機 0912-345-678。\n'
    '美華自述最近胸悶，收縮壓 162 mmHg。\n家屬王先生表示會陪同回診，聯絡電話 08-7370002 分機121。',
    '姓名\t電話\t地址\n王大明\t0912345678\t新北市板橋區文化路一段100號\n林美華\t08-7370002\t屏東縣潮州鎮光華路12號',
    '',
]

# 換回真名：全形括號、括號內空白、對照表沒有的代號、自訂代號
REPLY_MAP = {'[姓名1]': '王大明', '[姓名10]': '林美華', '[電話1]': '0912345678', 'CASE-A': '個案甲'}
REPLIES = ['請[姓名1]回電[電話1]', '［姓名1］與【姓名10】', '[ 姓名1 ] 已約', '[姓名2] 不在對照表', 'CASE-A 已結案', '']

NODE_RUNNER = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[process.argv.length - 1], 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const sandbox = {};
// module 設成 undefined，走和瀏覽器一樣的路徑
new Function('sandbox', 'module', scripts[0] + '\n' + scripts[1].replace('(this)', '(sandbox)') + '\nsandbox.PLACES = PLACES;')(sandbox);
const engine = sandbox.IdMaskEngine.create(sandbox.PLACES);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = input.cases.map(t => {
  const plain = engine.scan(t).map(f => [f.kind, f.start, f.end, f.value]);
  const withKnown = engine.scan(t, input.known).map(f => [f.kind, f.start, f.end, f.value]);
  const m = engine.mask(t, input.known);
  return {plain, withKnown, masked: m.text, mapping: m.mapping, back: engine.unmask(m.text, m.mapping),
          residual: engine.residual(m.text, input.known).length};
});
const replies = input.replies.map(r => engine.unmask(r, input.map));
process.stdout.write(JSON.stringify({cases: out, replies}));
"""


def py_findings(text, known=None):
    return [[f.kind, f.start, f.end, f.value] for f in idmask.scan(text, known)]


class BuildTest(unittest.TestCase):
    def test_built_file_is_current(self):
        self.assertEqual((ROOT / '個資馬賽克.html').read_text(encoding='utf-8'), build_app.build(),
                         '成品不是最新的，請執行 python scripts/build_app.py')

    def test_no_network(self):
        html = build_app.build()
        self.assertIn("connect-src 'none'", html)
        for bad in ['http://', 'https://cdn', '<link ', 'src="http', 'fetch(', 'XMLHttpRequest']:
            self.assertNotIn(bad, html.replace('https://data.gov.tw/dataset/7441', ''))


@unittest.skipUnless(shutil.which('node'), '沒有 Node.js，跳過 JavaScript 比對')
class ParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.dumps({'cases': CASES, 'known': KNOWN, 'replies': REPLIES, 'map': REPLY_MAP},
                             ensure_ascii=False).encode('utf-8')
        p = subprocess.run(['node', '-e', NODE_RUNNER, str(ROOT / '個資馬賽克.html')], input=payload,
                           capture_output=True, check=True)
        out = json.loads(p.stdout.decode('utf-8'))
        cls.js, cls.replies = out['cases'], out['replies']

    def test_scan_same_as_python(self):
        for text, js in zip(CASES, self.js):
            with self.subTest(text=text):
                self.assertEqual(js['plain'], py_findings(text))
                self.assertEqual(js['withKnown'], py_findings(text, KNOWN))

    def test_mask_same_as_python(self):
        for text, js in zip(CASES, self.js):
            with self.subTest(text=text):
                r = idmask.mask(text, KNOWN)
                self.assertEqual(js['masked'], r.text)
                self.assertEqual(js['mapping'], r.mapping)
                self.assertEqual(js['back'], text)
                self.assertEqual(js['residual'], 0)

    def test_unmask_same_as_python(self):
        for text, js in zip(REPLIES, self.replies):
            with self.subTest(text=text):
                self.assertEqual(js, idmask.unmask(text, REPLY_MAP))


if __name__ == '__main__':
    unittest.main()
