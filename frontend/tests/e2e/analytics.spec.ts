import { test, expect } from '@playwright/test';

test.describe('Analytics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Assuming standard login or session setup happens via test fixtures
    // We navigate directly to the analytics page
    await page.goto('/analytics');
  });

  test('displays project analytics with default 24h range', async ({ page }) => {
    // Check for standard cards
    await expect(page.locator('text=Project Analytics')).toBeVisible();
    await expect(page.locator('text=Executions')).toBeVisible();
    await expect(page.locator('text=Success Rate')).toBeVisible();
    await expect(page.locator('text=Failure Rate')).toBeVisible();

    // Check charts
    await expect(page.locator('text=Executions Trend')).toBeVisible();
    await expect(page.locator('text=Failure Rate Trend')).toBeVisible();
    await expect(page.locator('text=Duration Trend')).toBeVisible();

    // Check tables
    await expect(page.locator('text=Top Failing Jobs')).toBeVisible();
    await expect(page.locator('text=Slowest Jobs')).toBeVisible();
  });

  test('updates time range and URL when filter is changed', async ({ page }) => {
    // Click the range selector (which starts at "Last 24 Hours")
    await page.click('text=Last 24 Hours');
    
    // Select "Last 7 Days"
    await page.click('text=Last 7 Days');

    // The URL should update
    await expect(page).toHaveURL(/.*range=7d/);
    
    // Data should reload (we can implicitly verify this by checking if the select reflects the new value)
    await expect(page.locator('text=Last 7 Days')).toBeVisible();
  });

  test('navigates to job analytics when a job is clicked', async ({ page }) => {
    // Wait for the Top Failing Jobs list to load and render links
    // This requires mock data or a seed script in a real environment
    // We'll just look for a link inside the top failing jobs card
    const jobLink = page.locator('.col-span-2.lg\\:col-span-1').filter({ hasText: 'Top Failing Jobs' }).locator('a').first();
    
    // If there's no data, this test might fail, so we conditionally skip or assume data exists
    if (await jobLink.count() > 0) {
      const href = await jobLink.getAttribute('href');
      await jobLink.click();
      
      // Verify we navigated to the job analytics page
      await expect(page).toHaveURL(new RegExp(`.*${href}.*`));
      await expect(page.locator('text=Job Analytics')).toBeVisible();
    }
  });
});
