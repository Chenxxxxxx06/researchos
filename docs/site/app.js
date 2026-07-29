/* ResearchOS — scroll reveal + Visual Editor demo */

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
  document.querySelectorAll('.reveal').forEach(function (el) {
    observer.observe(el);
  });

  // ═══ Visual Editor ═══

  // ── Tab switching ──
  var tabs = document.querySelectorAll('.ve-tab');
  var panels = document.querySelectorAll('.ve-panel');

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) { t.classList.remove('active'); });
      tab.classList.add('active');

      var target = tab.dataset.panel;
      panels.forEach(function (p) {
        p.classList.toggle('ve-panel-active', p.id === 'panel-' + target);
      });
    });
  });

  // ── Drag & Drop cards ──
  var cardsContainer = document.getElementById('ve-cards');
  if (cardsContainer) {
    var cards = cardsContainer.querySelectorAll('.ve-card');
    var dragged = null;

    cards.forEach(function (card) {
      card.addEventListener('dragstart', function (e) {
        dragged = this;
        this.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.id);
        // Hide default ghost on some browsers
        var ghost = this.cloneNode(true);
        ghost.style.position = 'absolute';
        ghost.style.top = '-9999px';
        document.body.appendChild(ghost);
        e.dataTransfer.setDragImage(ghost, 0, 0);
        setTimeout(function () { document.body.removeChild(ghost); }, 0);
      });

      card.addEventListener('dragend', function () {
        this.classList.remove('dragging');
        cardsContainer.querySelectorAll('.ve-card').forEach(function (c) {
          c.classList.remove('drag-over');
        });
        dragged = null;
      });

      card.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (this !== dragged) {
          this.classList.add('drag-over');
        }
      });

      card.addEventListener('dragleave', function () {
        this.classList.remove('drag-over');
      });

      card.addEventListener('drop', function (e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        if (dragged && dragged !== this) {
          // Insert the dragged card before this one
          cardsContainer.insertBefore(dragged, this);
        }
      });

      // ── Click to select → Inspector ──
      card.addEventListener('click', function (e) {
        // Don't select if we're dragging
        if (e.detail === 0) return;

        cards.forEach(function (c) { c.classList.remove('selected'); });
        this.classList.add('selected');

        updateInspector(this);
      });
    });

    // Prevent drag on text inside cards
    cardsContainer.addEventListener('dragstart', function (e) {
      if (e.target.tagName === 'STRONG' || e.target.tagName === 'SMALL' || e.target.tagName === 'SPAN') {
        e.preventDefault();
        return false;
      }
    });
  }

  // ── Inspector panel ──
  function updateInspector(card) {
    var body = document.getElementById('ve-inspector-body');
    if (!body) return;

    var name = card.dataset.name || '';
    var status = card.dataset.status || '';
    var gpu = card.dataset.gpu || '';
    var eta = card.dataset.eta || '';
    var id = card.dataset.id || '';

    var statusLabel = { running: '● Running', queued: '○ Queued', done: '✓ Done', paused: '⏸ Paused' }[status] || status;

    body.innerHTML =
      '<div class="ve-inspector-field">' +
        '<label>Name</label>' +
        '<input type="text" value="' + escapeHtml(name) + '" />' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>Status</label>' +
        '<div class="ve-inspector-value">' + statusLabel + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>GPU</label>' +
        '<input type="text" value="' + escapeHtml(gpu) + '" />' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>ETA</label>' +
        '<div class="ve-inspector-value">' + escapeHtml(eta) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>Priority</label>' +
        '<input type="range" min="1" max="10" value="' + id + '" />' +
        '<div style="display:flex;justify-content:space-between;color:var(--muted);font-size:.65rem"><span>Low</span><span>High</span></div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>Actions</label>' +
        '<div style="display:flex;flex-direction:column;gap:6px">' +
          '<a href="#" class="button button-small" style="width:100%;text-align:center;text-decoration:none" onclick="return false">▶ Resume</a>' +
          '<a href="#" class="button button-small button-ghost" style="width:100%;text-align:center;text-decoration:none;color:var(--muted)!important" onclick="return false">⏹ Stop</a>' +
        '</div>' +
      '</div>';
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Outline section click ──
  document.querySelectorAll('.ve-section-head').forEach(function (sec) {
    sec.addEventListener('click', function () {
      var fold = this.querySelector('.ve-fold');
      if (fold.textContent === '▸') {
        fold.textContent = '▾';
        this.style.background = 'rgba(107,230,184,.04)';
      } else {
        fold.textContent = '▸';
        this.style.background = '';
      }
    });
  });

  // ── Terminal typing loop ──
  var terminal = document.getElementById('ve-terminal');
  if (terminal) {
    var lines = [
      '<span class="prompt">$</span> researchos experiment run our-method --seed 99',
      '<span class="muted">[14:30:12]</span> ✓ container started · gpu:1 · 18GB free',
      '<span class="muted">[14:30:14]</span> ✓ checkpoint loaded · epoch 5/10',
      '<span class="muted">[14:30:20]</span> ◉ training · loss 0.112 · acc 0.921',
      '<span class="warn">[14:32:45]</span> ⚠ validation loss plateau · lr reduced to 1e-5'
    ];
    var lineIdx = 0;
    var typingLine = null;

    function addNextLine() {
      if (lineIdx >= lines.length) {
        // Restart after delay
        setTimeout(function () {
          terminal.innerHTML = '';
          lineIdx = 0;
          addNextLine();
        }, 3000);
        return;
      }

      var div = document.createElement('div');
      div.className = 've-term-line';
      div.innerHTML = lines[lineIdx];
      terminal.appendChild(div);
      lineIdx++;

      // Remove old typing class
      if (typingLine) typingLine.classList.remove('typing');

      // Add typing cursor to last line
      var allLines = terminal.querySelectorAll('.ve-term-line');
      var lastLine = allLines[allLines.length - 1];
      if (lastLine) {
        lastLine.classList.add('typing');
        // Rebuild inner HTML to include cursor
        lastLine.innerHTML = lastLine.innerHTML.replace('<span class="ve-cursor">▌</span>', '') + ' <span class="ve-cursor">▌</span>';
        typingLine = lastLine;
      }

      setTimeout(addNextLine, 1800 + Math.random() * 1200);
    }

    // Start after 2s
    setTimeout(function () {
      terminal.innerHTML = '';
      lineIdx = 0;
      addNextLine();
    }, 2000);
  }
})();
