import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };
const PRIMARY_ROUTES = ['missions', 'research', 'ide', 'experiments', 'paper', 'release', 'overview'] as const;

interface Timing {
  segment: string;
  duration_ms: number;
}

function percentile(values: number[], ratio: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(sorted.length * ratio) - 1)] ?? 0;
}

async function navigateSweep(page: import('@playwright/test').Page): Promise<Timing[]> {
  const timings: Timing[] = [];
  for (const segment of PRIMARY_ROUTES) {
    const link = page.locator(`[data-nav-segment="${segment}"]`).first();
    await expect(link).toBeVisible();
    await link.hover();
    const started = performance.now();
    await link.click();
    await page.waitForURL(new RegExp(`/projects/[^/]+/${segment}(?:\\?.*)?$`));
    await expect(page.locator(`[data-nav-segment="${segment}"]`).first()).toHaveAttribute('aria-current', 'page');
    timings.push({ segment, duration_ms: Math.round((performance.now() - started) * 100) / 100 });
  }
  return timings;
}

test.describe('local interaction performance', () => {
  test('core route clicks and pooled API stay within the responsiveness budget', async ({ page }) => {
    test.setTimeout(90_000);

    await page.goto('/login');
    await page.fill('input[type="email"]', DEMO.email);
    await page.fill('input[type="password"]', DEMO.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/projects');

    const project = page
      .locator('a[href*="/projects/"][href*="/overview"]')
      .filter({ hasText: 'ResearchOS Demo' })
      .first();
    await project.click();
    await page.waitForURL('**/overview');
    await expect(page.locator('[data-nav-segment="overview"]').first()).toHaveAttribute('aria-current', 'page');

    // Let production Link prefetches settle, then capture both a first-use and
    // an in-memory-cache sweep. A dev server is intentionally not accepted by
    // this gate because on-demand compilation is the regression it prevents.
    await page.waitForTimeout(1_500);
    const cold = await navigateSweep(page);
    const warm = await navigateSweep(page);

    const apiDurations = await page.evaluate(async () => {
      const samples: number[] = [];
      for (let index = 0; index < 12; index += 1) {
        const started = performance.now();
        const response = await fetch('http://localhost:8000/auth/me', { credentials: 'include' });
        if (!response.ok) throw new Error(`GET /auth/me returned ${response.status}`);
        await response.json();
        samples.push(performance.now() - started);
      }
      return samples;
    });

    const report = {
      measured_at: new Date().toISOString(),
      cold,
      warm,
      summary: {
        cold_p95_ms: percentile(cold.map((item) => item.duration_ms), 0.95),
        warm_p95_ms: percentile(warm.map((item) => item.duration_ms), 0.95),
        warm_max_ms: Math.max(...warm.map((item) => item.duration_ms)),
        api_p95_ms: Math.round(percentile(apiDurations, 0.95) * 100) / 100,
      },
    };

    const artifactDir = path.resolve(process.cwd(), '../../artifacts/performance');
    await mkdir(artifactDir, { recursive: true });
    await writeFile(path.join(artifactDir, 'latest.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
    console.log(`PERFORMANCE_REPORT ${JSON.stringify(report.summary)}`);

    expect(report.summary.cold_p95_ms).toBeLessThan(1_500);
    expect(report.summary.warm_p95_ms).toBeLessThan(800);
    expect(report.summary.warm_max_ms).toBeLessThan(1_000);
    expect(report.summary.api_p95_ms).toBeLessThan(150);
  });
});
