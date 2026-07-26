import { test, expect, type Page } from '@playwright/test';

/**
 * Design-system e2e: theme persistence + FOUC guard, command palette,
 * g-sequences, dialog a11y, toast. Runs against the seeded demo stack
 * (same credentials as e2e/smoke.spec.ts).
 */

const DEMO = { email: 'demo@researchos.dev', password: 'demo-password-123' };

async function login(page: Page): Promise<string> {
  await page.goto('/login');
  await page.fill('input[type="email"]', DEMO.email);
  await page.fill('input[type="password"]', DEMO.password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/projects');
  const projLink = page.locator('a[href*="/projects/"][href*="/overview"]').first();
  await projLink.click();
  await page.waitForURL('**/overview');
  const match = page.url().match(/\/projects\/([^/]+)/);
  if (!match?.[1]) throw new Error('Could not find projectId in URL');
  return match[1];
}

test.describe('design system', () => {
  test.beforeEach(async ({ page }) => {
    // Deterministic English labels regardless of the zh-CN default locale.
    await page.addInitScript(() => {
      window.localStorage.setItem('ros_locale', 'en-US');
    });
  });

  test('theme toggle persists across reloads (localStorage path)', async ({ page }) => {
    await login(page);
    await page.getByRole('button', { name: 'Theme' }).click();
    await page.getByRole('menuitemradio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

    // Back to light so later runs start clean.
    await page.getByRole('button', { name: 'Theme' }).click();
    await page.getByRole('menuitemradio', { name: 'Light' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });

  test('FOUC guard: boot script stamps data-theme before hydration', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('ros-theme', 'dark');
    });
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    // Evaluated at domcontentloaded — before client JS settles.
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    expect(theme).toBe('dark');
  });

  test('command palette: mod+k, fuzzy search, run navigates', async ({ page }) => {
    const projectId = await login(page);

    await page.keyboard.press('Control+KeyK');
    const combobox = page.getByRole('combobox');
    await expect(combobox).toBeVisible();
    await expect(combobox).toBeFocused();

    await combobox.fill('ide');
    const firstOption = page.getByRole('option').first();
    await expect(firstOption).toContainText(/IDE/i);

    await page.keyboard.press('Enter');
    await page.waitForURL(`**/projects/${projectId}/ide`);
  });

  test('g-sequences navigate; typing g in the palette does not', async ({ page }) => {
    const projectId = await login(page);

    // g then e → experiments.
    await page.keyboard.press('g');
    await page.keyboard.press('e');
    await page.waitForURL(`**/projects/${projectId}/experiments`);

    // Inside the palette input, g/e must only filter, never navigate.
    await page.keyboard.press('Control+KeyK');
    const combobox = page.getByRole('combobox');
    await expect(combobox).toBeVisible();
    await combobox.press('g');
    await combobox.press('e');
    await page.waitForTimeout(400);
    expect(page.url()).toContain(`/projects/${projectId}/experiments`);
    await page.keyboard.press('Escape');
  });

  test('dialog a11y: Esc closes the palette and restores focus', async ({ page }) => {
    await login(page);

    const paletteButton = page.getByRole('button', { name: /Search/ });
    await paletteButton.click();
    await expect(page.getByRole('combobox')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('combobox')).toBeHidden();
    await expect(paletteButton).toBeFocused();
  });

  test('toast: appears in the live region and auto-dismisses', async ({ page }) => {
    await login(page);

    const hasHook = await page.evaluate(() => typeof window.__rosToast === 'function');
    test.skip(!hasHook, 'toast test hook is only installed in dev builds');

    await page.evaluate(() => {
      window.__rosToast?.({ title: 'E2E toast', duration: 1500 });
    });
    const status = page.getByRole('status').filter({ hasText: 'E2E toast' });
    await expect(status).toBeVisible();
    await expect(status).toBeHidden({ timeout: 5000 });
  });
});
