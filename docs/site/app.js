/* ResearchOS — i18n · theme · Visual Editor · scroll reveal */
(function () {
  'use strict';

  /* ═══════════════════════════════════════════════
     i18n — Chinese / English
     ═══════════════════════════════════════════════ */
  var I18N = {
    'zh-CN': {
      'skip-link': '跳到主要内容',
      'nav-why': '为什么',
      'nav-harness': 'Harness',
      'nav-demo': 'Demo',
      'nav-cli': 'CLI',
      'nav-status': '状态',
      'hero-eyebrow': '以证据链为核心的科研 Agent 平台',
      'hero-title-part1': '你的研究循环，',
      'hero-title-part2': '终于连接在一起。',
      'hero-desc': '将论文、Idea、代码、实验、图表、稿件和评审连接成可暂停、可恢复、可审查的科研工作流。模型可以更换，证据链不会丢失。',
      'hero-cta1': '探索 Harness',
      'hero-cta2': '阅读架构 ↗',
      'hero-term-title': 'researchos — mission',
      'why-index': '01 / 为什么',
      'why-quote': '"论文里的这条结论，来自哪篇文献、哪个实验、哪个 commit 和哪份 artifact？"',
      'why-text': '科研工具彼此割裂，聊天记录又无法承担科学证据。ResearchOS 的核心不是生成更多文字，而是让每个公开主张最终指向可核查的工作过程。',
      'harness-index': '02 / HARNESS',
      'harness-heading': '一个上下文。<br/>多个专家 Agent。',
      'harness-desc': 'Coordinator 只负责拆解、调度、验证和合并。每个专项 Agent 拥有明确 Artifact，所有高风险动作经过人工闸门。',
      'principle1-title': 'Provenance-first',
      'principle1-desc': 'Claim → Evidence → Run → Artifact → Commit。模型输出默认只是候选。',
      'principle2-title': 'Context with boundaries',
      'principle2-desc': '规则、科学事实、会话和学习者记忆分层管理，不做一个混乱的"大向量库"。',
      'principle3-title': 'Human-governed',
      'principle3-desc': 'Scope、Evidence、Release 三道闸门。证据不足、预算耗尽或重复失败就停止。',
      'demo-index': '03 / VISUAL EDITOR',
      'demo-heading': 'Design mode.<br/>Drag. Click. Edit.',
      'demo-desc': '像操作 Figma 一样管理你的研究工作流。拖拽卡片调整优先级，点击选中查看溯源详情，每个 Agent 产出可追溯的 Artifact。',
      'demo-tab-canvas': 'Mission Canvas',
      'demo-tab-evidence': 'Evidence Graph',
      'demo-tab-terminal': 'Terminal',
      'demo-badge': 'Design Mode',
      'canvas-header': '📋 Agent Pipeline',
      'canvas-hint': 'drag to reorder · click to inspect',
      'evidence-header': '⌁ Provenance Chain',
      'evidence-hint': 'Claim → Evidence → Run → Artifact → Commit',
      'terminal-header': '⬛ Terminal',
      'terminal-hint': 'researchos agent log',
      'inspector-title': '🔍 Inspector',
      'inspector-hint': '← 点击左侧卡片查看 Agent 详情<br/>拖拽卡片调整任务优先级',
      'inspector-agent': 'Agent',
      'inspector-domain': '领域',
      'inspector-task': '任务',
      'inspector-status': '状态',
      'inspector-artifact': 'Artifact',
      'inspector-gate': '闸门',
      'inspector-commit': '关联 Commit',
      'inspector-provenance': '溯源链',
      'inspector-actions': '操作',
      'inspector-resume': '▶ 继续',
      'inspector-stop': '⏹ 停止',
      'inspector-priority': '优先级',
      'cli-index': '04 / TERMINAL',
      'cli-heading': '从终端启动<br/>科研 Harness。',
      'cli-desc': '同一个 API 服务于 Web、IDE 和 CLI。当前 alpha 已支持登录、项目切换、Agent Turn、交互会话、上下文查看、科研记忆与 Mission scaffold。',
      'cli-link': 'CLI 与记忆设计 ↗',
      'status-index': '05 / ALPHA STATUS',
      'status-heading': 'Built honestly.',
      'status-desc': '当前版本用于架构验证和共同设计。没有完成的能力会明确进入 TODO。',
      'status-col1-title': 'Research workspace',
      'status-col1-desc': 'Zotero、Copilot、Inbox、受限终端、实验进度、LaTeX、Reviewer、Release Studio、CLI。',
      'status-col2-title': 'Durable mission',
      'status-col2-desc': '数据库 DAG、Agent lease/heartbeat、Prompt/Skill Registry、Context retrieval evaluation。',
      'status-col3-title': 'Isolated execution',
      'status-col3-desc': 'Container、SSH/HPC/Slurm、真实 LaTeX、可复现重跑、多模态论文解析。',
      'cta-index': "LET'S BUILD",
      'cta-heading': 'Models will change.<br/>Research memory should survive.',
      'cta-desc': '欢迎讨论科研 Agent、实验基础设施、论文教育与可复现工作流。',
      'footer-left': 'ResearchOS · 0.1.0-alpha.1',
      'footer-right': '© 2024–2026 Chenxxxxxx06 · All Rights Reserved',
      'status-available': 'AVAILABLE SKELETON',
      'status-building': 'BUILDING',
      'status-planned': 'PLANNED',
      'github-text': 'GitHub ↗',
      'lang-label': 'EN',
      'agent-research': 'Research Agent',
      'agent-code': 'Code Agent',
      'agent-experiment': 'Experiment Agent',
      'agent-paper': 'Paper Agent',
      'agent-release': 'Release Agent',
      'domain-research': 'Zotero · Evidence',
      'domain-code': 'Patch · Git',
      'domain-experiment': 'DAG · Provenance',
      'domain-paper': 'LaTeX · Claims',
      'domain-release': 'Review · Story Pack',
      'task-research': '文献调研：低资源多模态分类',
      'task-code': '基线实现与代码框架',
      'task-experiment': '消融实验与指标追踪',
      'task-paper': '论文撰写与 Claim 溯源',
      'task-release': '内部评审与发布打包',
      'detail-research': '23 篇文献索引 · 5 个创新缺口 · arXiv + Semantic Scholar',
      'detail-code': '3 次 commit · 12 个文件变更 · 2 个 Patch 已合并',
      'detail-experiment': '5 组配置 · 3 个 seed · 8/15 运行完成 · 最佳 acc 91.2%',
      'detail-paper': '6 个章节 · 4 个已完成 · 2 个等待实验结果 · LaTeX 编译通过',
      'detail-release': 'Reviewer Arena 待触发 · 代码发布准备中 · 等待实验完成',
      'artifact-research': 'literature-review.md · 23 篇参考文献',
      'artifact-code': '3 commits · 12 files · 2 patches merged',
      'artifact-experiment': '8/15 runs complete · best acc 91.2%',
      'artifact-paper': 'draft-v2.tex · 4 figures placed · 1 table',
      'artifact-release': 'Awaiting experiment completion',
      'gate-approved': '已批准',
      'gate-pending': '待审批',
      'gate-blocked': '已阻塞',
      'gate-none': '—',
      'status-running': '● 运行中',
      'status-queued': '○ 排队中',
      'status-done': '✓ 已完成',
      'status-paused': '⏸ 已暂停',
      'ev-claim': 'Claim',
      'ev-evidence': 'Evidence',
      'ev-run': 'Run',
      'ev-artifact': 'Artifact',
      'ev-commit': 'Commit',
      'ev-claim-detail': '"Our method improves over baseline"',
      'ev-evidence-detail': 'Table 3: +2.3% on benchmark',
      'ev-run-detail': 'run-42 on A100-1 · seed 42',
      'ev-artifact-detail': 'results.json · figure-3.pdf',
      'ev-commit-detail': 'commit a1b2c3d · git log',
      'agent-flow-1': 'Research',
      'agent-flow-2': 'Code',
      'agent-flow-3': 'Experiment',
      'agent-flow-4': 'Paper',
      'agent-flow-5': 'Release',
      'flow-domain-1': 'Zotero · Evidence',
      'flow-domain-2': 'Patch · Git',
      'flow-domain-3': 'DAG · Provenance',
      'flow-domain-4': 'LaTeX · Claims',
      'flow-domain-5': 'Review · Story Pack',
    },
    'en': {
      'skip-link': 'Skip to main content',
      'nav-why': 'Why',
      'nav-harness': 'Harness',
      'nav-demo': 'Demo',
      'nav-cli': 'CLI',
      'nav-status': 'Status',
      'hero-eyebrow': 'Provenance-first scientific agent harness',
      'hero-title-part1': 'Your research loop,',
      'hero-title-part2': 'finally connected.',
      'hero-desc': 'Connect papers, ideas, code, experiments, figures, manuscripts, and reviews into a pausable, resumable, auditable research workflow. Models will change — the evidence chain survives.',
      'hero-cta1': 'Explore the Harness',
      'hero-cta2': 'Read Architecture ↗',
      'hero-term-title': 'researchos — mission',
      'why-index': '01 / WHY',
      'why-quote': '"Which paper, experiment, commit, and artifact does this claim trace back to?"',
      'why-text': 'Research tools are fragmented, and chat logs cannot serve as scientific evidence. ResearchOS is not about generating more text — it is about making every public claim point to a verifiable work process.',
      'harness-index': '02 / HARNESS',
      'harness-heading': 'One context.<br/>Specialist agents.',
      'harness-desc': 'The Coordinator only decomposes, schedules, verifies, and merges. Each specialist Agent owns one artifact type. Every high-risk action passes through a human gate.',
      'principle1-title': 'Provenance-first',
      'principle1-desc': 'Claim → Evidence → Run → Artifact → Commit. Model output is merely a candidate by default.',
      'principle2-title': 'Context with boundaries',
      'principle2-desc': 'Rules, scientific facts, conversations, and learner memory are layered separately — not a messy "giant vector store."',
      'principle3-title': 'Human-governed',
      'principle3-desc': 'Three gates: Scope, Evidence, Release. Stop on insufficient evidence, budget exhaustion, or repeated failure.',
      'demo-index': '03 / VISUAL EDITOR',
      'demo-heading': 'Design mode.<br/>Drag. Click. Edit.',
      'demo-desc': 'Manage your research workflow like Figma. Drag cards to reorder priorities. Click to inspect provenance details. Every agent produces a traceable artifact.',
      'demo-tab-canvas': 'Mission Canvas',
      'demo-tab-evidence': 'Evidence Graph',
      'demo-tab-terminal': 'Terminal',
      'demo-badge': 'Design Mode',
      'canvas-header': '📋 Agent Pipeline',
      'canvas-hint': 'drag to reorder · click to inspect',
      'evidence-header': '⌁ Provenance Chain',
      'evidence-hint': 'Claim → Evidence → Run → Artifact → Commit',
      'terminal-header': '⬛ Terminal',
      'terminal-hint': 'researchos agent log',
      'inspector-title': '🔍 Inspector',
      'inspector-hint': '← Click a card to view agent details<br/>Drag cards to reorder task priority',
      'inspector-agent': 'Agent',
      'inspector-domain': 'Domain',
      'inspector-task': 'Task',
      'inspector-status': 'Status',
      'inspector-artifact': 'Artifact',
      'inspector-gate': 'Gate',
      'inspector-commit': 'Linked Commit',
      'inspector-provenance': 'Provenance',
      'inspector-actions': 'Actions',
      'inspector-resume': '▶ Resume',
      'inspector-stop': '⏹ Stop',
      'inspector-priority': 'Priority',
      'cli-index': '04 / TERMINAL',
      'cli-heading': 'A research harness<br/>from your terminal.',
      'cli-desc': 'One API serves Web, IDE, and CLI. The alpha already supports login, project switching, Agent Turn, interactive sessions, context viewing, research memory, and Mission scaffold.',
      'cli-link': 'CLI & Memory Design ↗',
      'status-index': '05 / ALPHA STATUS',
      'status-heading': 'Built honestly.',
      'status-desc': 'The current version is for architecture validation and co-design. Capabilities not yet complete are explicitly marked as TODO.',
      'status-col1-title': 'Research workspace',
      'status-col1-desc': 'Zotero, Copilot, Inbox, restricted terminal, experiment progress, LaTeX, Reviewer, Release Studio, CLI.',
      'status-col2-title': 'Durable mission',
      'status-col2-desc': 'Database DAG, Agent lease/heartbeat, Prompt/Skill Registry, Context retrieval evaluation.',
      'status-col3-title': 'Isolated execution',
      'status-col3-desc': 'Container, SSH/HPC/Slurm, real LaTeX, reproducible reruns, multimodal paper parsing.',
      'cta-index': "LET'S BUILD",
      'cta-heading': 'Models will change.<br/>Research memory should survive.',
      'cta-desc': 'Discuss research agents, experiment infrastructure, paper education, and reproducible workflows.',
      'footer-left': 'ResearchOS · 0.1.0-alpha.1',
      'footer-right': '© 2024–2026 Chenxxxxxx06 · All Rights Reserved',
      'status-available': 'AVAILABLE SKELETON',
      'status-building': 'BUILDING',
      'status-planned': 'PLANNED',
      'github-text': 'GitHub ↗',
      'lang-label': '中文',
      'agent-research': 'Research Agent',
      'agent-code': 'Code Agent',
      'agent-experiment': 'Experiment Agent',
      'agent-paper': 'Paper Agent',
      'agent-release': 'Release Agent',
      'domain-research': 'Zotero · Evidence',
      'domain-code': 'Patch · Git',
      'domain-experiment': 'DAG · Provenance',
      'domain-paper': 'LaTeX · Claims',
      'domain-release': 'Review · Story Pack',
      'task-research': 'Literature Review: Low-resource Multimodal Classification',
      'task-code': 'Baseline Implementation & Code Framework',
      'task-experiment': 'Ablation Study & Metric Tracking',
      'task-paper': 'Manuscript Drafting & Claim Provenance',
      'task-release': 'Internal Review & Release Packaging',
      'detail-research': '23 papers indexed · 5 innovation gaps · arXiv + Semantic Scholar',
      'detail-code': '3 commits · 12 files changed · 2 patches merged',
      'detail-experiment': '5 configs · 3 seeds · 8/15 runs complete · best acc 91.2%',
      'detail-paper': '6 sections · 4 drafted · 2 pending results · LaTeX compiles',
      'detail-release': 'Reviewer Arena pending · code release ready · awaiting experiments',
      'artifact-research': 'literature-review.md · 23 references',
      'artifact-code': '3 commits · 12 files · 2 patches merged',
      'artifact-experiment': '8/15 runs complete · best acc 91.2%',
      'artifact-paper': 'draft-v2.tex · 4 figures placed · 1 table',
      'artifact-release': 'Awaiting experiment completion',
      'gate-approved': 'Approved',
      'gate-pending': 'Pending',
      'gate-blocked': 'Blocked',
      'gate-none': '—',
      'status-running': '● Running',
      'status-queued': '○ Queued',
      'status-done': '✓ Done',
      'status-paused': '⏸ Paused',
      'ev-claim': 'Claim',
      'ev-evidence': 'Evidence',
      'ev-run': 'Run',
      'ev-artifact': 'Artifact',
      'ev-commit': 'Commit',
      'ev-claim-detail': '"Our method improves over baseline"',
      'ev-evidence-detail': 'Table 3: +2.3% on benchmark',
      'ev-run-detail': 'run-42 on A100-1 · seed 42',
      'ev-artifact-detail': 'results.json · figure-3.pdf',
      'ev-commit-detail': 'commit a1b2c3d · git log',
      'agent-flow-1': 'Research',
      'agent-flow-2': 'Code',
      'agent-flow-3': 'Experiment',
      'agent-flow-4': 'Paper',
      'agent-flow-5': 'Release',
      'flow-domain-1': 'Zotero · Evidence',
      'flow-domain-2': 'Patch · Git',
      'flow-domain-3': 'DAG · Provenance',
      'flow-domain-4': 'LaTeX · Claims',
      'flow-domain-5': 'Review · Story Pack',
    }
  };

  var currentLang = localStorage.getItem('researchos-lang') || 'zh-CN';

  function t(key) {
    var dict = I18N[currentLang] || I18N['zh-CN'];
    return dict[key] || I18N['en'][key] || key;
  }

  function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      el.innerHTML = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
    });
    document.querySelectorAll('[data-i18n-value]').forEach(function (el) {
      el.setAttribute('value', t(el.getAttribute('data-i18n-value')));
    });
    document.querySelectorAll('[data-i18n-href]').forEach(function (el) {
      // href with i18n text content
    });
    // Update lang attribute on html
    document.documentElement.lang = currentLang;

    // Update lang toggle button text
    var langBtn = document.getElementById('lang-toggle');
    if (langBtn) {
      langBtn.textContent = t('lang-label');
    }
  }

  /* ═══════════════════════════════════════════════
     Theme — Dark / Light / System
     ═══════════════════════════════════════════════ */
  var THEME_KEY = 'researchos-theme';
  var currentTheme = localStorage.getItem(THEME_KEY) || 'system';

  function applyTheme(theme) {
    if (theme === 'system') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
    currentTheme = theme;
    localStorage.setItem(THEME_KEY, theme);
    updateThemeIcon();
  }

  function cycleTheme() {
    var next = { dark: 'light', light: 'system', system: 'dark' };
    applyTheme(next[currentTheme] || 'dark');
  }

  function updateThemeIcon() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var icons = { dark: '☀️', light: '🌙', system: '💻' };
    btn.textContent = icons[currentTheme] || '💻';
    btn.setAttribute('aria-label', 'Theme: ' + currentTheme);
  }

  /* ═══════════════════════════════════════════════
     Scroll Reveal
     ═══════════════════════════════════════════════ */
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

  /* ═══════════════════════════════════════════════
     Visual Editor — Mission Canvas
     ═══════════════════════════════════════════════ */

  // ── Agent mission data (mirrors real ResearchOS pipeline) ──
  var missionSteps = [
    {
      id: 'research',
      icon: '🔍',
      agentKey: 'agent-research',
      domainKey: 'domain-research',
      taskKey: 'task-research',
      detailKey: 'detail-research',
      artifactKey: 'artifact-research',
      status: 'done',
      gate: 'scope',
      gateStatus: 'approved',
      commit: 'a1b2c3d',
      commitMsg: 'docs: add literature survey with 23 refs',
      provenance: 'Claim → Evidence → Run → Artifact → Commit',
    },
    {
      id: 'code',
      icon: '💻',
      agentKey: 'agent-code',
      domainKey: 'domain-code',
      taskKey: 'task-code',
      detailKey: 'detail-code',
      artifactKey: 'artifact-code',
      status: 'done',
      gate: null,
      gateStatus: null,
      commit: 'e4f5g6h',
      commitMsg: 'feat: add baseline models and data pipeline',
      provenance: 'Claim → Evidence → Run → Artifact → Commit',
    },
    {
      id: 'experiment',
      icon: '🧪',
      agentKey: 'agent-experiment',
      domainKey: 'domain-experiment',
      taskKey: 'task-experiment',
      detailKey: 'detail-experiment',
      artifactKey: 'artifact-experiment',
      status: 'running',
      gate: 'evidence',
      gateStatus: 'pending',
      commit: 'i7j8k9l',
      commitMsg: 'exp: ablation study configs and run tracker',
      provenance: 'Claim → Evidence → Run → Artifact → Commit',
    },
    {
      id: 'paper',
      icon: '📝',
      agentKey: 'agent-paper',
      domainKey: 'domain-paper',
      taskKey: 'task-paper',
      detailKey: 'detail-paper',
      artifactKey: 'artifact-paper',
      status: 'queued',
      gate: null,
      gateStatus: null,
      commit: 'm0n1o2p',
      commitMsg: 'wip: draft sections 1-4, place 4 figures',
      provenance: 'Claim → Evidence → Run → Artifact → Commit',
    },
    {
      id: 'release',
      icon: '🚀',
      agentKey: 'agent-release',
      domainKey: 'domain-release',
      taskKey: 'task-release',
      detailKey: 'detail-release',
      artifactKey: 'artifact-release',
      status: 'paused',
      gate: 'release',
      gateStatus: 'blocked',
      commit: null,
      commitMsg: null,
      provenance: 'Claim → Evidence → Run → Artifact → Commit',
    },
  ];

  // ── Evidence chain data ──
  var evidenceChain = [
    { id: 'claim', icon: '💡', labelKey: 'ev-claim', detailKey: 'ev-claim-detail' },
    { id: 'evidence', icon: '📊', labelKey: 'ev-evidence', detailKey: 'ev-evidence-detail' },
    { id: 'run', icon: '⚡', labelKey: 'ev-run', detailKey: 'ev-run-detail' },
    { id: 'artifact', icon: '📦', labelKey: 'ev-artifact', detailKey: 'ev-artifact-detail' },
    { id: 'commit', icon: '🔗', labelKey: 'ev-commit', detailKey: 'ev-commit-detail' },
  ];

  // ── Build mission cards ──
  function buildMissionCards() {
    var container = document.getElementById('ve-cards');
    if (!container) return;
    container.innerHTML = '';

    missionSteps.forEach(function (step, idx) {
      var card = document.createElement('div');
      card.className = 've-card';
      card.setAttribute('draggable', 'true');
      card.setAttribute('data-id', step.id);
      card.setAttribute('data-idx', idx);

      var gateClass = step.gateStatus === 'approved' ? 'approved' :
                      step.gateStatus === 'pending' ? 'pending' :
                      step.gateStatus === 'blocked' ? 'blocked' : 'none';

      var gateLabelKey = step.gateStatus === 'approved' ? 'gate-approved' :
                         step.gateStatus === 'pending' ? 'gate-pending' :
                         step.gateStatus === 'blocked' ? 'gate-blocked' : 'gate-none';

      var statusLabelKey = 'status-' + step.status;

      card.innerHTML =
        '<div class="ve-card-drag">⠿</div>' +
        '<div class="ve-card-body">' +
          '<div class="ve-card-header-row">' +
            '<span class="ve-card-icon">' + step.icon + '</span>' +
            '<strong>' + t(step.agentKey) + '</strong>' +
            '<span class="ve-status-dot ' + step.status + '"></span>' +
            (step.gate ? '<span class="ve-card-gate ' + gateClass + '" data-i18n="' + gateLabelKey + '">' + t(gateLabelKey) + '</span>' : '') +
          '</div>' +
          '<small>' + t(step.domainKey) + ' · ' + t(step.taskKey) + '</small>' +
          '<small style="color:var(--muted)">' + t(step.detailKey) + '</small>' +
          '<span class="ve-card-status ' + step.status + '" data-i18n="' + statusLabelKey + '">' + t(statusLabelKey) + '</span>' +
        '</div>';

      container.appendChild(card);
    });

    // Re-attach drag events
    attachCardEvents();
  }

  // ── Build evidence graph ──
  function buildEvidenceGraph() {
    var container = document.getElementById('ve-evidence');
    if (!container) return;
    container.innerHTML = '';

    evidenceChain.forEach(function (node, i) {
      var el = document.createElement('div');
      el.className = 've-ev-node' + (i === 2 ? ' active' : '');
      el.setAttribute('data-ev', node.id);
      el.innerHTML =
        '<span class="ve-ev-icon">' + node.icon + '</span>' +
        '<span class="ve-ev-label" data-i18n="' + node.labelKey + '">' + t(node.labelKey) + '</span>' +
        '<span class="ve-ev-detail" data-i18n="' + node.detailKey + '">' + t(node.detailKey) + '</span>';

      container.appendChild(el);

      // Arrow between nodes
      if (i < evidenceChain.length - 1) {
        var arrow = document.createElement('span');
        arrow.className = 've-ev-arrow';
        arrow.textContent = '→';
        container.appendChild(arrow);
      }
    });

    // Click handler for evidence nodes
    container.querySelectorAll('.ve-ev-node').forEach(function (node) {
      node.addEventListener('click', function () {
        container.querySelectorAll('.ve-ev-node').forEach(function (n) { n.classList.remove('active'); });
        this.classList.add('active');
        updateEvidenceInspector(this.getAttribute('data-ev'));
      });
    });
  }

  function updateEvidenceInspector(evId) {
    var body = document.getElementById('ve-inspector-body');
    if (!body) return;

    var node = evidenceChain.find(function (n) { return n.id === evId; });
    if (!node) return;

    var details = {
      claim: {
        desc: currentLang === 'zh-CN' ? '从论文 Introduction 提取的科学主张' : 'Scientific claim extracted from paper Introduction',
        source: 'draft-v2.tex §2.1',
        verified: currentLang === 'zh-CN' ? '待实验验证' : 'Pending experiment verification',
      },
      evidence: {
        desc: currentLang === 'zh-CN' ? '支撑 Claim 的实验数据或文献引用' : 'Experimental data or citation supporting the claim',
        source: 'experiment run-42 / Table 3',
        verified: currentLang === 'zh-CN' ? 'p < 0.01 · 3 次重复' : 'p < 0.01 · 3 replicates',
      },
      run: {
        desc: currentLang === 'zh-CN' ? '产生 Evidence 的具体实验运行' : 'The specific experiment run that produced the evidence',
        source: 'A100-1 · seed=42 · 2026-07-29 14:02 UTC',
        verified: currentLang === 'zh-CN' ? 'DAG 完整 · 可复现' : 'DAG complete · reproducible',
      },
      artifact: {
        desc: currentLang === 'zh-CN' ? '运行产出的不可变文件' : 'Immutable files produced by the run',
        source: 'results.json · figure-3.pdf · metrics.csv',
        verified: currentLang === 'zh-CN' ? 'SHA256 已校验' : 'SHA256 verified',
      },
      commit: {
        desc: currentLang === 'zh-CN' ? 'Artifact 关联的 Git commit' : 'Git commit linked to the artifact',
        source: 'a1b2c3d · 2026-07-29 15:30 UTC',
        verified: currentLang === 'zh-CN' ? '已推送到 origin' : 'Pushed to origin',
      },
    };

    var d = details[evId] || details.claim;
    var label = t(node.labelKey);

    body.innerHTML =
      '<div class="ve-inspector-field">' +
        '<label>' + label + '</label>' +
        '<div class="ve-inspector-value">' + d.desc + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>' + (currentLang === 'zh-CN' ? '来源' : 'Source') + '</label>' +
        '<div class="ve-inspector-value mono">' + escapeHtml(d.source) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label>' + (currentLang === 'zh-CN' ? '验证状态' : 'Verification') + '</label>' +
        '<div class="ve-inspector-value">' + d.verified + '</div>' +
      '</div>' +
      '<div class="ve-provenance">' +
        evidenceChain.map(function (n, i) {
          return '<span>' + t(n.labelKey) + '</span>' + (i < evidenceChain.length - 1 ? ' → ' : '');
        }).join('') +
      '</div>';
  }

  // ── Card drag & drop ──
  function attachCardEvents() {
    var container = document.getElementById('ve-cards');
    if (!container) return;

    var cards = container.querySelectorAll('.ve-card');
    var dragged = null;

    cards.forEach(function (card) {
      card.addEventListener('dragstart', function (e) {
        dragged = this;
        this.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.id);
        var ghost = this.cloneNode(true);
        ghost.style.position = 'absolute';
        ghost.style.top = '-9999px';
        document.body.appendChild(ghost);
        e.dataTransfer.setDragImage(ghost, 0, 0);
        setTimeout(function () { document.body.removeChild(ghost); }, 0);
      });

      card.addEventListener('dragend', function () {
        this.classList.remove('dragging');
        container.querySelectorAll('.ve-card').forEach(function (c) {
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
          container.insertBefore(dragged, this);
        }
      });

      // Click to select → Inspector
      card.addEventListener('click', function (e) {
        if (e.detail === 0) return;
        cards.forEach(function (c) { c.classList.remove('selected'); });
        this.classList.add('selected');
        updateInspector(this);
      });
    });

    // Prevent drag on child text elements
    container.addEventListener('dragstart', function (e) {
      if (e.target.tagName === 'STRONG' || e.target.tagName === 'SMALL' ||
          e.target.tagName === 'SPAN' || e.target.tagName === 'DIV') {
        if (!e.target.classList.contains('ve-card')) {
          e.preventDefault();
          return false;
        }
      }
    });
  }

  // ── Inspector panel ──
  function updateInspector(card) {
    var body = document.getElementById('ve-inspector-body');
    if (!body) return;

    var idx = parseInt(card.getAttribute('data-idx'));
    var step = missionSteps[idx];
    if (!step) return;

    var statusLabelKey = 'status-' + step.status;
    var gateLabelKey = step.gateStatus === 'approved' ? 'gate-approved' :
                       step.gateStatus === 'pending' ? 'gate-pending' :
                       step.gateStatus === 'blocked' ? 'gate-blocked' : 'gate-none';

    var gateBadge = step.gate
      ? '<span class="ve-card-gate ' + (step.gateStatus || 'none') + '">' + t(gateLabelKey) + '</span>'
      : '<span class="ve-card-gate none">' + t('gate-none') + '</span>';

    body.innerHTML =
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-agent">' + t('inspector-agent') + '</label>' +
        '<div class="ve-inspector-value">' + step.icon + ' ' + t(step.agentKey) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-domain">' + t('inspector-domain') + '</label>' +
        '<div class="ve-inspector-value">' + t(step.domainKey) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-task">' + t('inspector-task') + '</label>' +
        '<div class="ve-inspector-value">' + t(step.taskKey) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-status">' + t('inspector-status') + '</label>' +
        '<div class="ve-inspector-value">' + t(statusLabelKey) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-artifact">' + t('inspector-artifact') + '</label>' +
        '<div class="ve-inspector-value mono">' + t(step.artifactKey) + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-gate">' + t('inspector-gate') + '</label>' +
        gateBadge +
      '</div>' +
      (step.commit ?
        '<div class="ve-inspector-field">' +
          '<label data-i18n="inspector-commit">' + t('inspector-commit') + '</label>' +
          '<div class="ve-inspector-value mono">' + escapeHtml(step.commit) + '<br/><small style="color:var(--muted)">' + escapeHtml(step.commitMsg) + '</small></div>' +
        '</div>' : '') +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-provenance">' + t('inspector-provenance') + '</label>' +
        '<div class="ve-provenance">' + step.provenance + '</div>' +
      '</div>' +
      '<div class="ve-inspector-field">' +
        '<label data-i18n="inspector-actions">' + t('inspector-actions') + '</label>' +
        '<div style="display:flex;flex-direction:column;gap:6px">' +
          '<a href="#" class="button button-small" style="width:100%;text-align:center;text-decoration:none" onclick="return false" data-i18n="inspector-resume">' + t('inspector-resume') + '</a>' +
          '<a href="#" class="button button-small button-ghost" style="width:100%;text-align:center;text-decoration:none" onclick="return false" data-i18n="inspector-stop">' + t('inspector-stop') + '</a>' +
        '</div>' +
      '</div>';
  }

  // ── Tab switching ──
  function setupTabs() {
    var tabs = document.querySelectorAll('.ve-tab');
    var panels = document.querySelectorAll('.ve-panel');

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');

        var target = tab.getAttribute('data-panel');
        panels.forEach(function (p) {
          p.classList.toggle('ve-panel-active', p.id === 'panel-' + target);
        });
      });
    });
  }

  // ── Terminal typing loop — uses real ResearchOS CLI ──
  function setupTerminal() {
    var terminal = document.getElementById('ve-terminal');
    if (!terminal) return;

    var lines = [
      '<span class="prompt">$</span> researchos mission run <span class="string">"低资源多模态分类"</span>',
      '<span class="muted">[14:02:03]</span> ✓ context  RESEARCHOS.md · verified memory · git state',
      '<span class="muted">[14:02:05]</span> ✓ plan     research → code → experiment → paper → release',
      '<span class="warn">[14:02:06]</span> ◇ gate     scope approval required before execution',
      '',
      '<span class="prompt">$</span> researchos experiment run ablation --seed 42',
      '<span class="muted">[14:02:10]</span> ✓ container started · gpu:0 · 22GB free',
      '<span class="muted">[14:02:12]</span> ✓ data loaded · 392,702 samples',
      '<span class="muted">[14:02:18]</span> ◉ run 5/15 · loss 0.147 · acc 0.912',
      '<span class="muted">[14:14:35]</span> ◉ run 8/15 · loss 0.112 · acc 0.921',
      '',
      '<span class="prompt">$</span> researchos context --render',
      '<span class="muted">[14:15:00]</span> claim → evidence → run → artifact → commit',
      '<span class="muted">[14:15:00]</span> 5 agents · 3 gates · 8 artifacts tracked',
    ];

    var lineIdx = 0;
    var typingLine = null;

    function addNextLine() {
      if (lineIdx >= lines.length) {
        setTimeout(function () {
          terminal.innerHTML = '';
          lineIdx = 0;
          addNextLine();
        }, 4000);
        return;
      }

      var div = document.createElement('div');
      div.className = 've-term-line';
      if (lines[lineIdx] === '') {
        div.innerHTML = '&nbsp;';
      } else {
        div.innerHTML = lines[lineIdx];
      }
      terminal.appendChild(div);
      lineIdx++;

      if (typingLine) typingLine.classList.remove('typing');

      var allLines = terminal.querySelectorAll('.ve-term-line');
      var lastLine = allLines[allLines.length - 1];
      if (lastLine && lines[lineIdx - 1] !== '') {
        lastLine.classList.add('typing');
        lastLine.innerHTML = lastLine.innerHTML.replace('<span class="ve-cursor">▌</span>', '') + ' <span class="ve-cursor">▌</span>';
        typingLine = lastLine;
      }

      var delay = lines[lineIdx - 1] === '' ? 600 : 1500 + Math.random() * 1000;
      setTimeout(addNextLine, delay);
    }

    setTimeout(function () {
      terminal.innerHTML = '';
      lineIdx = 0;
      addNextLine();
    }, 1500);
  }

  /* ═══════════════════════════════════════════════
     Init
     ═══════════════════════════════════════════════ */
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function init() {
    // Theme
    if (currentTheme !== 'system') {
      document.documentElement.setAttribute('data-theme', currentTheme);
    }
    updateThemeIcon();

    var themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', cycleTheme);
    }

    // Language
    document.documentElement.lang = currentLang;
    var langBtn = document.getElementById('lang-toggle');
    if (langBtn) {
      langBtn.addEventListener('click', function () {
        currentLang = currentLang === 'zh-CN' ? 'en' : 'zh-CN';
        localStorage.setItem('researchos-lang', currentLang);
        applyI18n();
        buildMissionCards();
        buildEvidenceGraph();
      });
    }

    // Apply i18n
    applyI18n();

    // Build Visual Editor
    buildMissionCards();
    buildEvidenceGraph();
    setupTabs();
    setupTerminal();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
