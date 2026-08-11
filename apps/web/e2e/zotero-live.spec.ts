import { expect, test } from '@playwright/test';

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };
const libraryId = process.env.ZOTERO_TEST_USER;
const apiKey = process.env.ZOTERO_TEST_KEY;

test.describe('Zotero live integration', () => {
  test.skip(!libraryId || !apiKey, 'Set ZOTERO_TEST_USER and ZOTERO_TEST_KEY to run.');

  test('save, verify, sync, and expose imported papers', async ({ page }, testInfo) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', DEMO.email);
    await page.fill('input[type="password"]', DEMO.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/projects');
    await page.locator('a[href*="/projects/"][href*="/overview"]').first().click();
    await page.waitForURL('**/overview');
    const projectId = page.url().match(/\/projects\/([^/]+)/)?.[1];
    expect(projectId).toBeTruthy();

    await page.goto(`/projects/${projectId}/references`);
    await page.waitForLoadState('networkidle');

    const edit = page.getByRole('button', { name: '编辑' });
    if (await edit.isVisible()) await edit.click();
    await page.getByPlaceholder('例如 12345678').fill(libraryId!);
    await page.locator('input[type="password"]').fill(apiKey!);
    await page.getByRole('button', { name: '保存连接' }).click();
    await expect(page.getByText(/Key：\*\*\*\*/)).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: '检测权限' }).click();
    await expect(page.getByText(/Zotero key and library access verified/)).toBeVisible({
      timeout: 30_000,
    });

    await page.getByRole('button', { name: '同步文库' }).click();
    await expect(page.getByText(/已同步：新增/)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/尚未同步/)).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath('zotero-synced.png'), fullPage: true });
  });
});
