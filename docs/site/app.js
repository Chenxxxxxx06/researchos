/* ═══════════════════════════════════════════════
   ResearchOS — Language toggle
   ═══════════════════════════════════════════════ */

(function () {
  'use strict';

  var KEY = 'researchos-lang';
  var html = document.documentElement;

  function setLang(lang) {
    html.className = lang === 'en' ? 'lang-en' : 'lang-zh';
    try { localStorage.setItem(KEY, lang); } catch (_) {}
    var btns = document.querySelectorAll('.lang-btn');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].dataset.lang === lang);
    }
    html.lang = lang === 'en' ? 'en' : 'zh-CN';
  }

  var saved = 'zh';
  try { saved = localStorage.getItem(KEY) || 'zh'; } catch (_) {}
  setLang(saved);

  var btns = document.querySelectorAll('.lang-btn');
  for (var i = 0; i < btns.length; i++) {
    btns[i].addEventListener('click', function () {
      setLang(this.dataset.lang);
    });
  }
})();
