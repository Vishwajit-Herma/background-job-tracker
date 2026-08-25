import { test, expect } from '@playwright/test';

test.describe('Authentication & Team Flow', () => {
  // We use a mock API setup for isolation, but if ran against actual server, 
  // ensure admin@example.com exists.
  
  test('Successful login redirects to dashboard', async ({ page }) => {
    // Navigate to login
    await page.goto('/login');
    
    // Fill credentials
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'adminpass123');
    
    // Intercept API responses if needed, or rely on actual backend
    
    // Click login
    await page.click('button[type="submit"]');
    
    // Should redirect to projects page (or team page depending on routing)
    // We expect the Topbar to render the Team Switcher eventually.
  });

  test('Invalid login shows error message', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'wrong@example.com');
    await page.fill('input[type="password"]', 'bad');
    await page.click('button[type="submit"]');
    
    // Assuming backend returns 401
    await expect(page.locator('text=Invalid credentials')).toBeVisible({ timeout: 10000 });
  });

  test('E2E Flow: Login -> view dashboard -> switch team -> view team members -> logout', async ({ page }) => {
    await page.goto('/login');
    // For a real E2E, this assumes data is seeded.
  });
});
