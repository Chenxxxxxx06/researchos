import { expect, test, type Page } from '@playwright/test';

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };

async function login(page: Page): Promise<string> {
  await page.addInitScript(() => window.localStorage.setItem('ros_locale', 'en-US'));
  await page.goto('/login');
  await page.fill('input[type="email"]', DEMO.email);
  await page.fill('input[type="password"]', DEMO.password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/projects');
  const project = page.locator('a[href*="/projects/"][href*="/overview"]').first();
  const href = await project.getAttribute('href');
  const id = href?.match(/\/projects\/([^/]+)/)?.[1];
  if (!id) throw new Error('Demo project id not found.');
  return id;
}

test.describe('teacher requirement mission chain', () => {
  test('seeded mission exposes review, experiment, SQL, citation, voice, and management surfaces', async ({ page }, testInfo) => {
    const projectId = await login(page);
    await page.goto(`/projects/${projectId}/missions`);
    const missionRow = page.getByTestId('mission-row').filter({ hasText: 'Document AI / Low-resource learning' });
    await expect(missionRow).toBeVisible();
    const missionId = await missionRow.getAttribute('data-mission-id');
    if (!missionId) throw new Error('Seeded mission id not found.');

    await missionRow.click();
    await expect(page.getByText('Experiment plan').first()).toBeVisible();
    await expect(page.getByText(/Stage|Scope/i).first()).toBeVisible();

    await page.goto(`/projects/${projectId}/missions/${missionId}/review`);
    await expect(page.getByText(/review v1/i).first()).toBeVisible();
    await expect(page.getByText(/Claim.*evidence audit/i).first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mission-1-review.png'), fullPage: true });

    await page.goto(`/projects/${projectId}/missions/${missionId}/experiment-plan`);
    await expect(page.getByText('Variable design').first()).toBeVisible();
    await expect(page.getByText('Experiment matrix').first()).toBeVisible();
    await expect(page.getByText('RELEASE GATE').first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mission-2-plan.png'), fullPage: true });

    await page.goto(`/projects/${projectId}/missions/${missionId}/data-query`);
    await expect(page.getByText('READ-ONLY DATA LAB').first()).toBeVisible();
    await expect(page.getByText('Demo experiment metrics').first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mission-3-data-lab.png'), fullPage: true });

    await page.goto(`/projects/${projectId}/missions/${missionId}/citations`);
    await expect(page.getByText('CITATION ORGANIZER').first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mission-4-citations.png'), fullPage: true });

    await page.goto(`/projects/${projectId}/inbox`);
    await expect(page.getByTestId('streaming-voice-capture')).toBeVisible();

    await page.goto(`/projects/${projectId}/manage`);
    await expect(page.getByText('MANAGEMENT CENTER').first()).toBeVisible();
    await expect(page.getByText('Researchers').first()).toBeVisible();
    await expect(page.getByText('Experiment plans').first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mission-5-manage.png'), fullPage: true });
  });
});
