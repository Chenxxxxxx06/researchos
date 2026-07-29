/* ═══════════════════════════════════════════════
   ResearchOS — GitHub Pages
   Language toggle + scroll reveal
   ═══════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── Language ──
  const LANG_KEY = 'researchos-lang';
  const html = document.documentElement;

  function setLang(lang) {
    html.className = lang === 'en' ? 'lang-en' : 'lang-zh';
    localStorage.setItem(LANG_KEY, lang);
    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    // Update html lang attr for accessibility
    html.lang = lang === 'en' ? 'en' : 'zh-CN';
  }

  // Restore saved language or default to zh
  var saved = localStorage.getItem(LANG_KEY) || 'zh';
  setLang(saved);

  document.querySelectorAll('.lang-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setLang(this.dataset.lang);
    });
  });

  // ── Scroll Reveal ──
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.06 }
  );

  document.querySelectorAll('.reveal').forEach(function (el) {
    observer.observe(el);
  });

  // ── Smooth scroll for hash links ──
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
})();
