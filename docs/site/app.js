/* ResearchOS — scroll reveal + language toggle */

(function () {
  'use strict';

  // ── Scroll Reveal ──
  var observer = new IntersectionObserver(
    function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) {
          entries[i].target.classList.add('visible');
          observer.unobserve(entries[i].target);
        }
      }
    },
    { threshold: 0.08 }
  );

  var reveals = document.querySelectorAll('.reveal');
  for (var j = 0; j < reveals.length; j++) {
    observer.observe(reveals[j]);
  }

  // ── Language Toggle ──
  var KEY = 'researchos-lang';
  var html = document.documentElement;

  function setLang(lang) {
    html.className = lang === 'en' ? 'lang-en' : 'lang-zh';
    try { localStorage.setItem(KEY, lang); } catch (_) {}
    var btns = document.querySelectorAll('.lang-switch');
    for (var k = 0; k < btns.length; k++) {
      btns[k].classList.toggle('active', btns[k].dataset.lang === lang);
    }
    html.lang = lang === 'en' ? 'en' : 'zh-CN';
  }

  var saved = 'zh';
  try { saved = localStorage.getItem(KEY) || 'zh'; } catch (_) {}
  setLang(saved);

  var switches = document.querySelectorAll('.lang-switch');
  for (var m = 0; m < switches.length; m++) {
    switches[m].addEventListener('click', function () {
      setLang(this.dataset.lang);
    });
  }
})();
