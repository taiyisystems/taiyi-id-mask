"""測試資料都是虛構的。執行：python -m unittest discover -s tests -v"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import taiyi_id_mask as idmask  # noqa: E402
from taiyi_id_mask import cli, core  # noqa: E402

KNOWN = {'姓名': ['林美華'], '電話': ['0912-345-678'], '身分證號': ['T223456789']}


def kinds(text, known=None, extra=None):
    return [f.kind for f in idmask.scan(text, known, extra)]


class ScanTest(unittest.TestCase):
    def test_ids(self):
        self.assertIn('身分證號', kinds('身分證 A123456789 已核對'))
        self.assertIn('身分證號', kinds('新式統一證號 A800000014'))
        self.assertIn('身分證號', kinds('舊式居留證 AC01234567'))

    def test_phones_email(self):
        self.assertEqual(kinds('手機0912345678'), ['電話'])
        self.assertEqual(kinds('手機：0912345678'), ['標籤個資'])
        self.assertIn('電話', kinds('請撥 0912-345-678 聯絡'))
        self.assertIn('電話', kinds('衛生所 08-7370002 分機121'))
        self.assertIn('電話', kinds('+886 912 345 678'))
        self.assertIn('電子郵件', kinds('寄到 abc.def@example.com'))

    def test_dates(self):
        self.assertIn('日期', kinds('1958/03/12 出生'))
        self.assertIn('日期', kinds('民國47年3月12日'))
        self.assertIn('日期', kinds('115.11.06 回診'))

    def test_address(self):
        found = idmask.scan('住在屏東縣屏東市自由路272號3樓，獨居')
        self.assertEqual((found[0].kind, found[0].value), ('地址', '屏東縣屏東市自由路272號3樓'))
        self.assertIn('地址', kinds('台中市北區三民路三段129號'))
        self.assertIn('地址', kinds('花蓮縣秀林鄉富世村5鄰'))

    def test_place_name_alone_not_address(self):
        self.assertEqual(kinds('屏東縣衛生局轉介'), [])

    def test_names(self):
        self.assertIn('姓名', kinds('姓名：陳小明，男'))
        self.assertIn('姓名', kinds('王先生主訴胸悶'))
        self.assertIn('姓名', kinds('美華說最近頭暈', KNOWN))

    def test_known_values_take_priority(self):
        # 已知值要優先於其他規則，不能被較長的規則結果蓋掉而留下半個名字
        self.assertEqual(idmask.mask('聯絡人：王大明伯', {'姓名': ['王大明']}).text, '聯絡人：[姓名1]伯')
        self.assertEqual(idmask.mask('家屬：女兒陳美玲', {'姓名': ['陳美玲']}).text, '家屬：女兒[姓名1]')

    def test_labeled_name_skips_kin_word(self):
        self.assertEqual(idmask.mask('家屬：女兒陳美玲').text, '家屬：女兒[姓名1]')
        idmask.guard('家屬：女兒王大明，大明表示可陪同', {'姓名': ['王大明']})

    def test_clinical_values_not_masked(self):
        text = '收縮壓 162 mmHg，舒張壓 98，空腹血糖 135 mg/dL，HbA1c 7.2%，BMI 29.4，血壓 140/90，eGFR 48'
        self.assertEqual(idmask.scan(text), [])

    def test_long_numbers_and_labels(self):
        self.assertIn('長串數字', kinds('編號0012345678'))
        self.assertIn('標籤個資', kinds('病歷號：A0012345'))

    def test_extra_pattern(self):
        self.assertEqual(kinds('病歷 PT-12345 已建檔'), [])
        self.assertEqual(kinds('病歷 PT-12345 已建檔', extra=[('病歷號', r'PT-\d{5}')]), ['病歷號'])


class MaskTest(unittest.TestCase):
    def test_mask_and_unmask(self):
        text = '林美華（T223456789）電話 0912-345-678，美華自述胸悶。'
        r = idmask.mask(text, KNOWN)
        for v in ['林美華', 'T223456789', '0912-345-678', '美華']:
            self.assertNotIn(v, r.text)
        self.assertIn('[姓名1]', r.text)
        self.assertEqual(idmask.unmask(r.text, r.mapping), text)

    def test_unmask_tolerates_fullwidth_and_unknown_tokens(self):
        m = {'[姓名1]': '王大明', '[電話1]': '0912345678'}
        self.assertEqual(idmask.unmask('請［姓名1］回電【電話1】，[ 姓名1 ]已約', m), '請王大明回電0912345678，王大明已約')
        self.assertEqual(idmask.unmask('[姓名2] 不在對照表', m), '[姓名2] 不在對照表')
        self.assertEqual(idmask.unmask('[姓名10]', {'[姓名1]': '甲', '[姓名10]': '乙'}), '乙')

    def test_role_word_not_part_of_name(self):
        self.assertEqual(idmask.mask('家屬王先生表示會陪同').text, '家屬[姓名1]先生表示會陪同')
        self.assertEqual(idmask.mask('病人陳大明先生').text, '病人[姓名1]先生')

    def test_same_value_same_token(self):
        self.assertEqual(idmask.mask('王先生說王先生昨天沒吃藥').text.count('[姓名1]'), 2)

    def test_guard_passes_clean(self):
        r = idmask.guard('姓名：陳小明，住屏東縣潮州鎮光華路12號，血糖 180')
        self.assertNotIn('陳小明', r.text)
        self.assertNotIn('光華路12號', r.text)
        self.assertIn('血糖 180', r.text)

    def test_guard_blocks_residual(self):
        orig = core.mask
        try:
            core.mask = lambda text, known=None, extra=None: core.MaskResult(text, [], {})
            with self.assertRaises(idmask.PIIBlocked) as cm:
                core.guard('身分證 A123456789')
            self.assertEqual(cm.exception.residual[0].kind, '身分證號')
        finally:
            core.mask = orig


class RecordTest(unittest.TestCase):
    def test_minimize(self):
        rec = {'name': '林美華', 'id_no': 'T223456789', 'birth_date': '1958-03-12', 'sex': '女',
               'sbp': 162, 'dbp': 98, 'address': '屏東縣屏東市自由路272號'}
        out = idmask.minimize_record(rec, ['sex', 'sbp', 'dbp', 'age_band'], today=date(2026, 11, 6))
        self.assertEqual(out, {'sex': '女', 'sbp': 162, 'dbp': 98, 'age_band': '65-69 歲'})

    def test_age_band(self):
        self.assertEqual(idmask.age_band(date(1930, 1, 1), date(2026, 11, 6)), '90 歲以上')
        self.assertEqual(idmask.age_band(date(2000, 11, 7), date(2026, 11, 6)), '25-29 歲')


class CliTest(unittest.TestCase):
    def run_cli(self, text, *args):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'in.txt'
            p.write_text(text, encoding='utf-8')
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main([str(p), *args])
            return code, out.getvalue(), err.getvalue()

    def test_cli_mask(self):
        code, out, _ = self.run_cli('王先生 0912345678')
        self.assertEqual(code, 0)
        self.assertNotIn('0912345678', out)

    def test_cli_json(self):
        code, out, _ = self.run_cli('王先生 0912345678', '--json')
        data = json.loads(out)
        self.assertEqual({f['kind'] for f in data['findings']}, {'姓名', '電話'})
        self.assertNotIn('mapping', data)


if __name__ == '__main__':
    unittest.main()
