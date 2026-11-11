/* 個資偵測與遮蔽：src/taiyi_id_mask/core.py 的 JavaScript 版，給離線網頁用。
 * 規則必須和 core.py 一致；tests/test_app.py 用 Node 逐例比對兩邊結果。
 * 這裡只能用瀏覽器與 Node 都有的功能，不連網路。 */
(function (root) {
  'use strict';

  var CJK = '[一-鿿]';
  var NUM = '[0-9０-９一二三四五六七八九十百]+';

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&');
  }

  function create(places) {
    var counties = places.counties.concat(places.counties.map(function (c) { return c.replace(/臺/g, '台'); }));
    var alt = Array.from(new Set(counties.concat(places.towns)))
      .map(escapeRe).sort(function (a, b) { return b.length - a.length; }).join('|');

    // 內建偵測項目：[類別, 正規表示式]，順序同 core.PATTERNS
    var PATTERNS = [
      ['電子郵件', /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g],
      ['身分證號', /(?<![A-Za-z0-9])[A-Za-z][0-9]{9}(?![0-9])/g],
      ['身分證號', /(?<![A-Za-z0-9])[A-Za-z][A-Da-d][0-9]{8}(?![0-9])/g],
      ['電話', /(?<![0-9])(?:\+?886[-\s]?|0)9[0-9]{2}[-\s]?[0-9]{3}[-\s]?[0-9]{3}(?![0-9])/g],
      ['電話', /(?<![0-9])(?:\(0[2-8][0-9]{0,2}\)|0[2-8][0-9]{0,2})[-\s]?[0-9]{3,4}[-\s]?[0-9]{3,4}(?:[#分機轉]+[0-9]{1,5})?(?![0-9])/g],
      ['日期', /(?<![0-9])(?:19|20)[0-9]{2}[-\/.年](?:0?[1-9]|1[0-2])[-\/.月](?:0?[1-9]|[12][0-9]|3[01])日?(?![0-9])/g],
      ['日期', /(?:民國)?(?<![0-9])[0-9]{2,3}[-\/.年](?:0?[1-9]|1[0-2])[-\/.月](?:0?[1-9]|[12][0-9]|3[01])日?(?![0-9])/g],
      ['長串數字', /(?<![0-9])[0-9]{8,}(?![0-9])/g]
    ];
    var ADDRESS = new RegExp(
      '(?:' + alt + ')+' +
      '(?:' + CJK + '{1,4}?[村里])?(?:' + NUM + '鄰)?' +
      '(?:' + CJK + '{1,6}?(?:路|街|大道)(?:' + NUM + '段)?)?' +
      '(?:' + NUM + '巷)?(?:' + NUM + '弄)?(?:' + NUM + '(?:之' + NUM + ')?號)?(?:' + NUM + '樓(?:之' + NUM + ')?)?', 'g');
    var ADDRESS_PART = /[村里鄰路街道巷弄號樓]/;
    var PLACE_PREFIX = new RegExp('^(?:' + alt + ')+');
    var NAME_CHAR = '(?:(?![說的是和跟與位這那給向對請叫及或在有了到找問])[一-鿿])';
    // 「家屬王先生」「病人陳小姐」：前面的身分詞不算名字
    var ROLE = '(?:家屬|病人|個案|患者|案主|聯絡人|看護|鄰居|同事|朋友)';
    var HONORIFIC = new RegExp(ROLE + '?(' + NAME_CHAR + '{1,3})(?=先生|小姐|女士|太太|阿嬤|阿公|伯伯|阿姨|媽媽|爸爸)', 'g');
    // 「家屬：女兒陳美玲」：標籤後面的稱謂詞跳過，只取人名
    var KIN = '(?:女兒|兒子|媳婦|女婿|太太|先生|丈夫|妻子|配偶|母親|父親|媽媽|爸爸|孫子|孫女|弟弟|妹妹|哥哥|姊姊|姐姐|看護)';
    var LABELED_NAME = new RegExp('(?:姓名|病人|個案|患者|家屬|聯絡人)\\s*[:：]\\s*' + KIN + '?(?!' + KIN + ')(' + CJK + '{2,4})', 'g');
    var LABELED_ANY = /(?:身分證|身份證|統一證號|病歷號|健保卡|地址|住址|電話|手機|生日|出生)(?:字號|號碼|號)?\s*[:：]\s*([^\s，,。；;]{2,40})/g;
    var TOKEN = /^\[[^\[\]]+\d+\]$/;
    // 換回時也認得全形括號（［姓名1］、【姓名1】）和括號內的空白：別人或其他程式改寫回覆時常這樣
    var ANY_TOKEN = /[\[［【]\s*([^\[\]［］【】\s]+?\d+)\s*[\]］】]/g;

    function knownItems(known) {
      var items = [];
      Object.keys(known || {}).forEach(function (kind) {
        var values = known[kind];
        if (typeof values === 'string') values = [values];
        (values || []).forEach(function (v) {
          v = String(v).trim();
          if (v.length >= 2) items.push([kind, v]);
          // 三字以上的姓名，文字裡常只寫名字，名字也一起遮
          if (kind === '姓名' && v.length >= 3) items.push([kind, v.slice(1)]);
        });
      });
      return items.sort(function (a, b) { return b[1].length - a[1].length; });
    }

    // 群組 1 在這些規則裡都是比對結果的結尾，用長度推回位置
    function tail(m) { return m.index + m[0].length - m[1].length; }

    function scan(text, known, extra) {
      // 已知值最可靠，先佔位置；其他規則只能填在已知值以外的地方
      var first = [], c = first;
      function add(kind, start, value) { c.push({ kind: kind, start: start, end: start + value.length, value: value }); }
      knownItems(known).forEach(function (kv) {
        for (const m of text.matchAll(new RegExp(escapeRe(kv[1]), 'g'))) add(kv[0], m.index, m[0]);
      });
      c = [];
      for (const m of text.matchAll(LABELED_NAME)) add('姓名', tail(m), m[1]);
      for (const m of text.matchAll(LABELED_ANY)) add('標籤個資', tail(m), m[1]);
      (extra || []).map(function (e) { return [e[0], new RegExp(e[1].source || e[1], 'g')]; })
        .concat(PATTERNS).forEach(function (kp) {
          for (const m of text.matchAll(kp[1])) add(kp[0], m.index, m[0]);
        });
      for (const m of text.matchAll(ADDRESS)) {
        if (ADDRESS_PART.test(m[0].slice(PLACE_PREFIX.exec(m[0])[0].length))) add('地址', m.index, m[0]);
      }
      for (const m of text.matchAll(HONORIFIC)) add('姓名', tail(m), m[1]);
      function byLength(a, b) { return (b.end - b.start) - (a.end - a.start) || a.start - b.start; }
      var taken = [];
      first.sort(byLength).concat(c.sort(byLength)).forEach(function (f) {
        if (taken.every(function (t) { return f.end <= t.start || f.start >= t.end; })) taken.push(f);
      });
      return taken.sort(function (a, b) { return a.start - b.start; });
    }

    // 依指定的偵測結果換成代號；同一個原值用同一個代號
    function maskFindings(text, findings) {
      var mapping = {}, reverse = {}, counter = {}, out = [], pos = 0;
      findings.forEach(function (f) {
        var key = f.kind + '\u0000' + f.value;
        if (!(key in reverse)) {
          counter[f.kind] = (counter[f.kind] || 0) + 1;
          var token = '[' + f.kind + counter[f.kind] + ']';
          reverse[key] = token;
          mapping[token] = f.value;
        }
        out.push(text.slice(pos, f.start), reverse[key]);
        f.token = reverse[key];
        pos = f.end;
      });
      out.push(text.slice(pos));
      return { text: out.join(''), findings: findings, mapping: mapping };
    }

    function mask(text, known, extra) { return maskFindings(text, scan(text, known, extra)); }

    // 回覆切成片段：一般文字 {text}，代號 {token, value}（對照表沒有的代號 value 是 null）
    function unmaskParts(text, mapping) {
      var parts = [], pos = 0;
      for (const m of text.matchAll(ANY_TOKEN)) {
        var key = '[' + m[1] + ']';
        parts.push({ text: text.slice(pos, m.index) });
        parts.push({ token: m[0], value: Object.prototype.hasOwnProperty.call(mapping, key) ? mapping[key] : null });
        pos = m.index + m[0].length;
      }
      parts.push({ text: text.slice(pos) });
      return parts;
    }

    function unmask(text, mapping) {
      text = unmaskParts(text, mapping).map(function (p) {
        return 'token' in p ? (p.value === null ? p.token : p.value) : p.text;
      }).join('');
      // 不是 [類別數字] 形式的自訂代號，照原樣逐字換
      Object.keys(mapping).filter(function (t) { return !TOKEN.test(t); })
        .sort(function (a, b) { return b.length - a.length; }).forEach(function (t) {
          text = text.split(t).join(mapping[t]);
        });
      return text;
    }

    // 遮蔽後再掃一次，回傳殘留（空陣列＝通過）
    function residual(maskedText, known, extra) {
      return scan(maskedText, known, extra).filter(function (f) { return !TOKEN.test(f.value); });
    }

    return { scan: scan, mask: mask, maskFindings: maskFindings, unmask: unmask, unmaskParts: unmaskParts, residual: residual };
  }

  var api = { create: create };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.IdMaskEngine = api;
})(this);
