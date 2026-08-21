import { test, expect } from '@playwright/test';

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };

test.describe('ResearchOS smoke', () => {
  test('login and navigate all core pages', async ({ page }) => {
    test.setTimeout(90_000);
    // 1. Login
    await page.goto('/login');
    await expect(page).toHaveTitle(/ResearchOS/);
    await expect(page.getByRole('heading', { name: 'ResearchOS', exact: true })).toBeVisible();
    await page.fill('input[type="email"]', DEMO.email);
    await page.fill('input[type="password"]', DEMO.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/projects');

    // 2. Projects list
    await expect(page.locator('text=ResearchOS Demo').first()).toBeVisible();
    await page.screenshot({ path: 'artifacts/screenshots/1-login-success.png' });
    await page.screenshot({ path: 'artifacts/screenshots/2-projects.png' });

    // Get the demo project link
    const projLink = page.locator('a[href*="/projects/"][href*="/overview"]').filter({ hasText: 'ResearchOS Demo' }).first();
    await projLink.click();
    await page.waitForURL('**/overview');
    await expect(page.getByText(/RESEARCH LOOP/i).first()).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'artifacts/screenshots/3-overview.png' });

    // Extract projectId from URL
    const url = page.url();
    const match = url.match(/\/projects\/([^/]+)/);
    const projectId = match ? match[1] : '';
    if (!projectId) throw new Error('Could not find projectId in URL');

    // 3. Research Copilot
    await page.goto(`/projects/${projectId}/research`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('heading', { name: 'Research Copilot', exact: true })).toBeVisible({ timeout: 5000 });
    await expect(page.getByLabel(/模型|Model/)).toBeVisible();
    await page.screenshot({ path: 'artifacts/screenshots/4-research.png' });

    // 4. AI IDE
    await page.goto(`/projects/${projectId}/ide`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('button', { name: /资源管理器|Explorer/i }).first()).toBeVisible({ timeout: 10000 });
    const workspaceLabel = page.getByText('Workspace', { exact: true });
    await expect(workspaceLabel).toBeVisible();
    await workspaceLabel.locator('..').getByRole('button').first().click();
    await page.getByRole('button', { name: /设置文件夹/ }).click();
    await expect(page.getByText('本地项目文件夹的绝对路径')).toBeVisible();
    await expect(page.getByLabel('本地项目文件夹的绝对路径')).toBeVisible();
    await page.getByRole('button', { name: '取消' }).click();
    await page.screenshot({ path: 'artifacts/screenshots/5-ide.png' });

    // 5. Experiments
    await page.goto(`/projects/${projectId}/experiments`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('heading', { name: /实验面板|Experiments/i }).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/6-experiments.png' });

    // 6. Paper Workspace
    await page.goto(`/projects/${projectId}/paper`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('heading', { name: /AI 写作助手|AI Assistant/i })).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/7-paper.png' });

    // 7. References + Zotero
    await page.goto(`/projects/${projectId}/references`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(/Zotero|文献中心|References/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/8-references.png' });

    // 8. Research Inbox
    await page.goto(`/projects/${projectId}/inbox`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(/Research Inbox|科研收件箱/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/9-inbox.png' });

    // 9. Advanced Mission Control and venue deadlines remain available as
    // contextual tools instead of occupying the primary navigation rail.
    await page.goto(`/projects/${projectId}/orchestration`);
    await expect(page.getByRole('heading', { name: 'Mission Control' })).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'artifacts/screenshots/9b-orchestration.png' });

    await page.goto(`/projects/${projectId}/deadlines`);
    await expect(page.getByRole('heading', { name: /会议与期刊 DDL|Venue deadlines/i })).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'artifacts/screenshots/9c-deadlines.png' });

    // 11. Reviewer
    await page.goto(`/projects/${projectId}/reviewer`);
    await expect(page.getByText(/模拟审稿|Simulated review/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/10-reviewer.png' });

    // 12. Release Studio
    await page.goto(`/projects/${projectId}/release`);
    await expect(page.getByText(/Research Release Studio/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/11-release.png' });

    // 13. Settings
    await page.goto(`/projects/${projectId}/settings`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(/Language|语言|LLM/i).first()).toBeVisible({ timeout: 5000 });
    const editButton = page.getByRole('button', { name: /修改|Edit/ }).first();
    if (await editButton.isVisible()) {
      await editButton.click();
      await expect(page.locator('input[type="password"]')).toHaveValue('');
      await expect(page.getByText(/保留当前密钥|keep the current key/i)).toBeVisible();
      await page.getByRole('button', { name: /取消|Cancel/ }).click();
    }
    await page.screenshot({ path: 'artifacts/screenshots/12-settings.png' });

    // 14. Chinese interface (default)
    await page.goto(`/projects/${projectId}/overview`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(/项目总览|Research Copilot|project/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/13-chinese-default.png' });

    // 15. Switch to English through the accessible language menu.
    await page.getByRole('button', { name: /语言|Language/i }).click();
    await page.getByRole('menuitemradio', { name: 'English' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-US');
    await page.goto(`/projects/${projectId}/overview`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(/Overview|Evidence|Release Studio/i).first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'artifacts/screenshots/14-english.png' });
  });
});
