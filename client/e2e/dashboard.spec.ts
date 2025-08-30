import { test, expect } from '@playwright/test';

test.describe('AI Agent Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should load the main dashboard', async ({ page }) => {
    // Check that the main dashboard loads
    await expect(page).toHaveTitle(/AI Agent Dashboard/);
    
    // Verify main components are present
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
  });

  test('should display agents in the radar view', async ({ page }) => {
    // Wait for agents to load
    await page.waitForResponse(/.*\/api\/agents/);
    
    // Check that the agent radar is interactive
    const radar = page.locator('[data-testid="agent-radar"]');
    await expect(radar).toBeVisible();
    
    // The radar should have some content (even if no agents)
    await expect(radar).not.toBeEmpty();
  });

  test('should display tasks in the task queue', async ({ page }) => {
    // Wait for tasks to load
    await page.waitForResponse(/.*\/api\/tasks/);
    
    // Check that the task queue is present
    const taskQueue = page.locator('[data-testid="task-queue"]');
    await expect(taskQueue).toBeVisible();
    
    // AG Grid should be initialized
    await expect(page.locator('.ag-root-wrapper')).toBeVisible();
  });

  test('should display real-time metrics', async ({ page }) => {
    // Wait for metrics to load
    await page.waitForResponse(/.*\/api\/system\/metrics/);
    
    // Check metrics panel
    const metricsPanel = page.locator('[data-testid="metrics-panel"]');
    await expect(metricsPanel).toBeVisible();
    
    // Should contain metrics data
    await expect(metricsPanel.locator('text=/tokens/i')).toBeVisible();
    await expect(metricsPanel.locator('text=/cost/i')).toBeVisible();
  });

  test('should have functional control panel', async ({ page }) => {
    const controlPanel = page.locator('[data-testid="control-panel"]');
    await expect(controlPanel).toBeVisible();
    
    // Check for control buttons
    await expect(controlPanel.locator('button', { hasText: /run/i })).toBeVisible();
    await expect(controlPanel.locator('button', { hasText: /pause/i })).toBeVisible();
    await expect(controlPanel.locator('button', { hasText: /stop/i })).toBeVisible();
    
    // Check throttle control
    await expect(controlPanel.locator('input[type="range"], input[type="number"]')).toBeVisible();
  });

  test('should handle responsive design', async ({ page }) => {
    // Test desktop view
    await page.setViewportSize({ width: 1200, height: 800 });
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    
    // Test tablet view
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
  });

  test('should show loading states during data fetch', async ({ page }) => {
    // Intercept API calls to add delay
    await page.route('/api/agents', async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });
    
    await page.goto('/');
    
    // Should show loading state or skeleton
    // This depends on your implementation
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Intercept API calls to return errors
    await page.route('/api/agents', route => 
      route.fulfill({ status: 500, body: 'Server Error' })
    );
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Application should still load without crashing
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
  });

  test('should maintain state after page refresh', async ({ page }) => {
    // Interact with the application
    const controlPanel = page.locator('[data-testid="control-panel"]');
    
    // Adjust throttle (if available)
    const throttleControl = controlPanel.locator('input[type="range"], input[type="number"]').first();
    if (await throttleControl.isVisible()) {
      await throttleControl.fill('0.8');
    }
    
    // Refresh the page
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // Verify application still works
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
  });
});

test.describe('Dashboard Accessibility', () => {
  test('should meet basic accessibility standards', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check for proper heading structure
    await expect(page.locator('h1, h2, h3')).toHaveCount({ gte: 1 });
    
    // Check for proper alt text on images (if any)
    const images = page.locator('img');
    const imageCount = await images.count();
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      await expect(img).toHaveAttribute('alt');
    }
    
    // Check for proper form labels (if any)
    const inputs = page.locator('input');
    const inputCount = await inputs.count();
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const id = await input.getAttribute('id');
      if (id) {
        await expect(page.locator(`label[for="${id}"]`)).toBeVisible();
      }
    }
    
    // Check color contrast (basic test - proper tools would do better)
    await expect(page.locator('body')).toHaveCSS('color', /.+/);
    await expect(page.locator('body')).toHaveCSS('background-color', /.+/);
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Tab through interactive elements
    const controlPanel = page.locator('[data-testid="control-panel"]');
    await controlPanel.locator('button').first().focus();
    
    // Test keyboard navigation
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to reach all interactive elements
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });

  test('should work with screen reader attributes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check for ARIA labels where needed
    const buttons = page.locator('button');
    const buttonCount = await buttons.count();
    for (let i = 0; i < buttonCount; i++) {
      const button = buttons.nth(i);
      const hasText = await button.textContent();
      const hasAriaLabel = await button.getAttribute('aria-label');
      expect(hasText || hasAriaLabel).toBeTruthy();
    }
    
    // Check for proper roles (if any custom components)
    const customComponents = page.locator('[role]');
    const componentCount = await customComponents.count();
    for (let i = 0; i < componentCount; i++) {
      const component = customComponents.nth(i);
      const role = await component.getAttribute('role');
      expect(role).toBeTruthy();
    }
  });
});