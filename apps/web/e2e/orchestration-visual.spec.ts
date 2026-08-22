import { expect, test, type Page } from '@playwright/test';

const PROJECT_ID = 'project-demo';
const MISSION_ID = 'mission-demo';
const NOW = '2026-08-16T10:00:00Z';
const TASK_KEYS = [
  'scope',
  'discover',
  'read',
  'synthesize',
  'gap',
  'critic',
  'direction',
  'repository',
  'baseline',
  'coding',
  'experiment_plan',
  'experiment_run',
  'reproduce',
  'analyze',
  'write',
  'review',
  'release',
] as const;

const TITLES: Record<(typeof TASK_KEYS)[number], string> = {
  scope: 'Frame the research question',
  discover: 'Discover primary literature',
  read: 'Read evidence-bearing sections',
  synthesize: 'Synthesize claims and methods',
  gap: 'Map unresolved evidence gaps',
  critic: 'Challenge the proposed novelty',
  direction: 'Authorize a research direction',
  repository: 'Pin the reference repository',
  baseline: 'Reproduce the baseline',
  coding: 'Implement one bounded change',
  experiment_plan: 'Freeze the experiment plan',
  experiment_run: 'Run the controlled experiment',
  reproduce: 'Verify independent reproduction',
  analyze: 'Analyze results and limitations',
  write: 'Draft evidence-bound claims',
  review: 'Run adversarial paper review',
  release: 'Authorize the research release',
};

const tasks = TASK_KEYS.map((key, index) => ({
  id: `task-${index + 1}`,
  project_id: PROJECT_ID,
  mission_id: MISSION_ID,
  mission_step_id: null,
  parent_task_id: null,
  task_key: key,
  title: TITLES[key],
  role: index < 7 ? 'evidence_agent' : index < 11 ? 'builder_agent' : 'review_agent',
  agent_type: 'research_worker',
  status:
    index < 3
      ? 'completed'
      : index === 3
        ? 'running'
        : index === 5
          ? 'waiting_approval'
          : index === 6
            ? 'ready'
            : 'draft',
  priority: 100 - index,
  attempt: index < 5 ? 1 : 0,
  max_attempts: 3,
  idempotency_key: `mission:${MISSION_ID}:${key}`,
  input_json: { mission_topic: 'Evidence-grounded autonomous research systems' },
  output_json: {},
  acceptance_json: [
    'Every claim links to a verifiable artifact.',
    'Uncertainty and contradictory evidence remain explicit.',
  ],
  permissions_json: ['read:papers', 'write:artifacts'],
  budget_json: { max_tokens: 12000 },
  agent_run_id: index === 3 ? 'run-live-0001' : null,
  available_at: NOW,
  started_at: index < 4 ? NOW : null,
  finished_at: index < 3 ? NOW : null,
  last_error_json: null,
  created_at: NOW,
  updated_at: NOW,
}));

const graph = {
  mission_id: MISSION_ID,
  tasks,
  dependencies: tasks.slice(1).map((task, index) => ({
    id: `edge-${index + 1}`,
    task_id: task.id,
    depends_on_task_id: tasks[index]?.id,
    required_artifact_schema: null,
  })),
  artifacts: tasks.slice(0, 4).map((task, index) => ({
    id: `artifact-${index + 1}`,
    mission_id: MISSION_ID,
    task_id: task.id,
    schema_name: ['research_scope', 'paper_corpus', 'evidence_matrix', 'synthesis'][index],
    schema_version: 1,
    content_hash: `${index + 1}`.repeat(64),
    uri: `artifact://mission/${MISSION_ID}/${index + 1}`,
    metadata_json: {},
    producer_run_id: `run-${index + 1}`,
    visibility: 'mission',
    created_at: NOW,
  })),
  gates: [
    {
      id: 'gate-1',
      mission_id: MISSION_ID,
      task_id: 'task-6',
      gate_kind: 'novelty_review',
      status: 'pending',
      request_json: {},
      decision_json: {},
      requested_by: 'critic_agent',
      decided_by: null,
      decided_at: null,
      created_at: NOW,
    },
  ],
  events: tasks.slice(0, 7).map((task, index) => ({
    id: `event-${index + 1}`,
    task_id: task.id,
    seq: index + 1,
    event_type: index < 4 ? 'task.completed' : index === 4 ? 'task.running' : 'task.ready',
    payload_json: {},
    actor_id: 'orchestrator',
    message: `${task.title} state reconciled`,
    created_at: NOW,
  })),
  counts: { completed: 3, running: 1, waiting_approval: 1, ready: 1, draft: 11 },
  progress: {
    total_tasks: 17,
    completed_tasks: 3,
    running_tasks: 1,
    blocked_tasks: 11,
    failed_tasks: 0,
    progress_percent: 23.53,
    active_agents: [
      {
        task_id: 'task-4',
        task_key: 'synthesize',
        title: TITLES.synthesize,
        role: 'evidence_agent',
        agent_type: 'research',
        status: 'running',
        agent_run_id: 'run-live-0001',
        attempt: 1,
        started_at: NOW,
        progress_percent: 50,
        current_action: 'Synthesize claims and methods',
      },
    ],
    current_phase: 'review',
    next_ready_tasks: ['direction'],
    blocker_messages: [],
    eta_seconds: null,
    eta_basis: 'insufficient completed-task history',
  },
};

async function mockMissionControl(page: Page) {
  const dispatched: Array<Record<string, unknown>> = [];
  await page.context().addCookies([
    { name: 'ros_session', value: 'visual-test', domain: 'localhost', path: '/' },
  ]);
  await page.addInitScript(() => {
    window.localStorage.setItem('ros_locale', 'en-US');
    window.localStorage.setItem('ros-theme', 'light');
  });
  await page.route('http://localhost:8000/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path === '/auth/me') {
      body = {
        user: {
          id: 'user-demo',
          email: 'researcher@example.com',
          display_name: 'Researcher',
          avatar_url: null,
          created_at: NOW,
        },
        organizations: [{ id: 'org-demo', name: 'Research Lab', slug: 'lab', role: 'owner' }],
      };
    } else if (path === `/projects/${PROJECT_ID}/missions`) {
      body = {
        items: [
          {
            id: MISSION_ID,
            project_id: PROJECT_ID,
            topic: 'Evidence-grounded autonomous research systems',
            objective:
              'Condense literature into auditable directions, reproduce code, run bounded experiments and draft defensible claims.',
            field: 'Machine learning systems',
            status: 'active',
            current_step: 'review',
            scope_json: {},
            progress: 41,
            version: 3,
            last_activity_at: NOW,
            created_by: 'user-demo',
            updated_by: 'user-demo',
            created_at: NOW,
            updated_at: NOW,
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      };
    } else if (path === `/projects/${PROJECT_ID}/orchestration/missions/${MISSION_ID}`) {
      body = graph;
    } else if (path === `/projects/${PROJECT_ID}/agents/capabilities`) {
      body = [];
    } else if (path === `/projects/${PROJECT_ID}/missions/${MISSION_ID}/research-synthesis`) {
      body = {
        mission_id: MISSION_ID,
        paper_count: 0,
        reviewed_card_count: 0,
        tuple_count: 0,
        directions: [],
        benchmarks: [],
        generated_at: NOW,
      };
    } else if (path.endsWith('/research-loops')) {
      body = [];
    } else if (path === `/projects/${PROJECT_ID}/experiment-runs`) {
      body = [
        {
          id: 'baseline-run',
          experiment_id: 'experiment-1',
          project_id: PROJECT_ID,
          name: 'Pinned baseline',
          status: 'completed',
          git_commit: '89abcdef01234567',
          command: 'python train.py',
          config_json: {},
          progress: 100,
          started_at: NOW,
          finished_at: NOW,
          created_at: NOW,
        },
      ];
    } else if (
      path === `/projects/${PROJECT_ID}/orchestration/tasks/task-7/dispatch` &&
      route.request().method() === 'POST'
    ) {
      dispatched.push(route.request().postDataJSON() as Record<string, unknown>);
      body = {
        task_id: 'task-7',
        agent_run_id: 'run-dispatched',
        status: 'queued',
        stream: `/projects/${PROJECT_ID}/agent-runs/run-dispatched/stream`,
      };
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'access-control-allow-origin': 'http://localhost:3000',
        'access-control-allow-credentials': 'true',
      },
      body: JSON.stringify(body),
    });
  });
  return { dispatched };
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test(`mission graph is connected and stable on ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    if (viewport.name === 'mobile') await page.emulateMedia({ reducedMotion: 'reduce' });
    const requests = await mockMissionControl(page);
    const errors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });

    await page.goto(`/projects/${PROJECT_ID}/orchestration`);
    await expect(page.getByRole('heading', { name: 'Mission Control' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Authorize a research direction/i })).toBeVisible();
    await page.getByRole('button', { name: /Authorize a research direction/i }).click();
    await expect(page.getByLabel('Agent task instruction')).toBeVisible();
    await page.getByLabel('Agent task instruction').fill('Verify artifacts, then dispatch the approved direction.');
    await page.getByLabel('Agent context JSON').fill('{"reviewed":true}');
    await page.getByRole('button', { name: 'Dispatch agent' }).click();
    await expect.poll(() => requests.dispatched.length).toBe(1);
    expect(requests.dispatched[0]).toEqual({
      message: 'Verify artifacts, then dispatch the approved direction.',
      context: { reviewed: true },
    });
    await page.getByRole('tab', { name: /Gates/i }).click();
    await expect(page.getByText('novelty_review')).toBeVisible();

    if (viewport.name === 'mobile') {
      const durationSeconds = await page.locator('.agent-flow-line.is-live').evaluate((element) => {
        const value = getComputedStyle(element).animationDuration;
        return value.endsWith('ms') ? Number.parseFloat(value) / 1000 : Number.parseFloat(value);
      });
      expect(durationSeconds).toBeLessThanOrEqual(0.001);
    }

    const overflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
    expect(errors).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`mission-control-${viewport.name}.png`),
      fullPage: true,
    });
  });
}
