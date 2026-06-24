import { test, expect } from '@playwright/test';

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };

test.describe('ResearchOS smoke', () => {
  test('login and navigate all core pages', async ({ page }) => {
    // 1. Login
    await page.goto('/login');
    await expect(page).toHaveTitle(/ResearchOS/);
    await expect(page.locator('text=ResearchOS')).toBeVisible();
    await page.fill('input[type="email"]', DEMO.email);
    await page.fill('input[type="password"]', DEMO.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/projects');
    await page.screenshot({ path: 'artifacts/screenshots/1-login-success.png' });

    // 2. Projects list
    await expect(page.locator('text=ResearchOS Demo').first()).toBeVisible();
    await page.screenshot({ path: 'artifacts/screenshots/2-projects.png' });

    // Get the demo project link
    const projLink = page.locator('a[href*="/projects/"][href*="/overview"]').first();
    await projLink.click();
    await page.waitForURL('**/overview');
    await expect(page.locator('text=Research Copilot').or(page.locator('text=ResearchOS Demo'))).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/3-overview.png' });

    // Extract projectId from URL
    const url = page.url();
    const match = url.match(/\/projects\/([^/]+)/);
    const projectId = match ? match[1] : '';
    if (!projectId) throw new Error('Could not find projectId in URL');

    // 3. Research Copilot
    await page.goto(`/projects/${projectId}/research`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Library').or(page.locator('text=Find papers'))).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/4-research.png' });

    // 4. AI IDE
    await page.goto(`/projects/${projectId}/ide`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Explorer').or(page.locator('text=No file open')).or(page.locator('.monaco-editor'))).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'artifacts/screenshots/5-ide.png' });

    // 5. Experiments
    await page.goto(`/projects/${projectId}/experiments`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/VLM|experiment|Select a run/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/6-experiments.png' });

    // 6. Paper Workspace
    await page.goto(`/projects/${projectId}/paper`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/AI Assistant|Compile|Preview|assistant/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/7-paper.png' });

    // 7. Skills Marketplace
    await page.goto(`/projects/${projectId}/skills`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Nature Writing|CVPR|skills|Builder/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/8-skills.png' });

    // 8. Skill Builder
    await page.goto(`/projects/${projectId}/skills/builder`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/builder|Builder|skill/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/9-skill-builder.png' });

    // 9. Settings
    await page.goto(`/projects/${projectId}/settings`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Language|语言|LLM/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/10-settings.png' });

    // 10. Chinese interface (default)
    await page.goto(`/projects/${projectId}/overview`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/项目总览|Research Copilot|project/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/11-chinese-default.png' });

    // 11. Switch to English
    const langSelect = page.locator('select[aria-label="语言"], select[aria-label="Language"]').first();
    if (await langSelect.isVisible()) {
      await langSelect.selectOption('en-US');
      await page.waitForTimeout(1000);
    }
    await page.goto(`/projects/${projectId}/overview`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Overview|Research Copilot|Sign out/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/12-english.png' });
  });
});
