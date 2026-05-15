import { expect, test } from '@playwright/test';

test('uses the warm Notebook visual language', async ({ page }) => {
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [], total: 0 })
    }));

    await page.goto('/');

    const bodyBackground = await page.locator('body').evaluate(element => getComputedStyle(element).backgroundImage);
    expect(bodyBackground).toContain('linear-gradient');

    const logoColor = await page.locator('.logo-title').evaluate(element => getComputedStyle(element).color);
    expect(logoColor).toBe('rgb(234, 88, 12)');

    const firstToolBackground = await page.getByRole('button', { name: /思维图谱/ }).evaluate(element => {
        const style = getComputedStyle(element);
        return `${style.backgroundImage} ${style.backgroundColor}`;
    });
    expect(firstToolBackground).toContain('linear-gradient');

    const generateBackground = await page.getByRole('button', { name: /生成/ }).evaluate(element => getComputedStyle(element).backgroundImage);
    expect(generateBackground).toContain('linear-gradient');

    await page.setViewportSize({ width: 1440, height: 900 });
    const generateButton = page.getByRole('button', { name: /生成播客/ });
    await expect(generateButton).toBeInViewport();
    const buttonBox = await generateButton.boundingBox();
    expect(buttonBox).not.toBeNull();
    expect(buttonBox!.y + buttonBox!.height).toBeLessThanOrEqual(900);
});
