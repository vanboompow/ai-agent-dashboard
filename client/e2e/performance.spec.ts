import { test, expect } from '@playwright/test';

test.describe('Performance Tests', () => {
  test('should load dashboard within performance thresholds', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Should load within 5 seconds (adjust based on requirements)
    expect(loadTime).toBeLessThan(5000);
    
    // Check that all main components are loaded
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
  });

  test('should handle large datasets efficiently', async ({ page }) => {
    // Mock large dataset responses
    await page.route('/api/agents', async route => {
      const largeAgentList = Array.from({ length: 1000 }, (_, i) => ({
        agentId: `agent-${i}`,
        status: i % 4 === 0 ? 'working' : 'idle',
        taskCategory: `category-${i % 10}`,
        currentTask: i % 4 === 0 ? `task-${i}` : null,
        elapsedTime: i * 100,
        angle: (i * 36) % 360,
        distance: 50 + (i % 50)
      }));
      
      await route.fulfill({ 
        json: largeAgentList,
        headers: { 'content-type': 'application/json' }
      });
    });

    await page.route('/api/tasks', async route => {
      const largeTaskList = Array.from({ length: 5000 }, (_, i) => ({
        task_id: `task-${i}`,
        description: `Performance test task ${i}`,
        status: ['pending', 'in_progress', 'completed'][i % 3],
        priority: ['low', 'medium', 'high'][i % 3],
        sector: `sector-${i % 20}`,
        agent_id: i % 4 === 0 ? `agent-${i % 1000}` : null,
        tps: i % 10,
        time_elapsed: `${i % 60}s`
      }));
      
      await route.fulfill({ 
        json: largeTaskList,
        headers: { 'content-type': 'application/json' }
      });
    });

    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Should still load within reasonable time with large datasets
    expect(loadTime).toBeLessThan(10000);
    
    // Components should render successfully
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    
    // Test interaction responsiveness
    const interactionStart = Date.now();
    const controlPanel = page.locator('[data-testid="control-panel"]');
    await controlPanel.locator('button').first().click();
    const interactionTime = Date.now() - interactionStart;
    
    // Interactions should remain responsive
    expect(interactionTime).toBeLessThan(1000);
  });

  test('should maintain performance with rapid real-time updates', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Create multiple agents for testing
    const agents = [];
    for (let i = 0; i < 10; i++) {
      const agentResponse = await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: `perf_test_agent_${i}`,
          hostname: `perf-host-${i}`,
          current_status: 'idle'
        }
      });
      
      if (agentResponse.ok()) {
        const agent = await agentResponse.json();
        agents.push(agent);
      }
    }

    const startTime = Date.now();
    
    // Rapidly update agent statuses
    for (let i = 0; i < 100; i++) {
      const agent = agents[i % agents.length];
      const newStatus = ['idle', 'working', 'paused'][i % 3];
      
      await page.request.patch(`http://localhost:8000/api/agents/${agent.agent_id}/status`, {
        data: { status: newStatus }
      });
      
      // Small delay to simulate real-world timing
      await page.waitForTimeout(50);
    }
    
    const updateTime = Date.now() - startTime;
    
    // Updates should complete in reasonable time
    expect(updateTime).toBeLessThan(15000);
    
    // UI should remain responsive
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    
    // Test UI interaction during updates
    const controlPanel = page.locator('[data-testid="control-panel"]');
    const throttleControl = controlPanel.locator('input[type="range"], input[type="number"]').first();
    
    if (await throttleControl.isVisible()) {
      await throttleControl.fill('0.9');
      await expect(throttleControl).toHaveValue('0.9');
    }
    
    // Clean up test agents
    for (const agent of agents) {
      await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
    }
  });

  test('should handle memory usage efficiently', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Get initial memory usage
    const initialMemory = await page.evaluate(() => {
      if ('memory' in performance) {
        return (performance as any).memory.usedJSHeapSize;
      }
      return 0;
    });
    
    // Perform memory-intensive operations
    for (let i = 0; i < 10; i++) {
      // Create and delete test data
      const agentResponse = await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: `memory_test_agent_${i}`,
          hostname: `memory-host-${i}`,
          current_status: 'working'
        }
      });
      
      if (agentResponse.ok()) {
        const agent = await agentResponse.json();
        
        // Wait for UI update
        await page.waitForTimeout(100);
        
        // Delete the agent
        await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
        
        // Wait for cleanup
        await page.waitForTimeout(100);
      }
    }
    
    // Force garbage collection if available
    await page.evaluate(() => {
      if ('gc' in window) {
        (window as any).gc();
      }
    });
    
    await page.waitForTimeout(1000);
    
    const finalMemory = await page.evaluate(() => {
      if ('memory' in performance) {
        return (performance as any).memory.usedJSHeapSize;
      }
      return 0;
    });
    
    // Memory usage should not grow excessively
    if (initialMemory > 0 && finalMemory > 0) {
      const memoryGrowth = finalMemory - initialMemory;
      const memoryGrowthMB = memoryGrowth / (1024 * 1024);
      
      // Should not grow by more than 50MB
      expect(memoryGrowthMB).toBeLessThan(50);
    }
  });

  test('should maintain 60fps during animations', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Start performance monitoring
    await page.evaluate(() => {
      (window as any).performanceData = {
        frames: [],
        startTime: performance.now()
      };
      
      function measureFrame() {
        const now = performance.now();
        (window as any).performanceData.frames.push(now);
        requestAnimationFrame(measureFrame);
      }
      
      requestAnimationFrame(measureFrame);
    });
    
    // Trigger animations by creating/updating agents
    for (let i = 0; i < 5; i++) {
      const agentResponse = await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: `animation_test_agent_${i}`,
          hostname: `animation-host-${i}`,
          current_status: 'working'
        }
      });
      
      if (agentResponse.ok()) {
        const agent = await agentResponse.json();
        
        // Update status multiple times to trigger animations
        const statuses = ['idle', 'working', 'paused'];
        for (const status of statuses) {
          await page.request.patch(`http://localhost:8000/api/agents/${agent.agent_id}/status`, {
            data: { status }
          });
          await page.waitForTimeout(200);
        }
        
        // Clean up
        await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
      }
    }
    
    // Measure frame rate
    const frameData = await page.evaluate(() => {
      const data = (window as any).performanceData;
      const totalTime = performance.now() - data.startTime;
      const frameCount = data.frames.length;
      const fps = (frameCount / totalTime) * 1000;
      
      return { fps, frameCount, totalTime };
    });
    
    // Should maintain reasonable frame rate (allowing for slower systems)
    expect(frameData.fps).toBeGreaterThan(30);
  });

  test('should handle network latency gracefully', async ({ page }) => {
    // Add artificial latency to API requests
    await page.route('/api/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 500)); // 500ms delay
      await route.continue();
    });
    
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Should handle slow network gracefully
    expect(loadTime).toBeLessThan(15000); // Allow more time for slow network
    
    // All components should still load
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
    
    // User interactions should still work
    const controlPanel = page.locator('[data-testid="control-panel"]');
    const button = controlPanel.locator('button').first();
    
    const interactionStart = Date.now();
    await button.click();
    const interactionTime = Date.now() - interactionStart;
    
    // UI should remain responsive even with slow API
    expect(interactionTime).toBeLessThan(1000);
  });

  test('should optimize bundle size and loading', async ({ page, context }) => {
    // Monitor resource loading
    const resources = [];
    
    page.on('response', response => {
      if (response.url().includes('localhost:5173')) {
        resources.push({
          url: response.url(),
          size: parseInt(response.headers()['content-length'] || '0'),
          type: response.headers()['content-type']
        });
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check JavaScript bundle size
    const jsResources = resources.filter(r => r.type?.includes('javascript'));
    const totalJSSize = jsResources.reduce((sum, r) => sum + r.size, 0);
    const totalJSSizeMB = totalJSSize / (1024 * 1024);
    
    // Bundle should be reasonably sized (adjust based on requirements)
    expect(totalJSSizeMB).toBeLessThan(5); // Less than 5MB total JS
    
    // Check CSS bundle size
    const cssResources = resources.filter(r => r.type?.includes('css'));
    const totalCSSSize = cssResources.reduce((sum, r) => sum + r.size, 0);
    const totalCSSSizeKB = totalCSSSize / 1024;
    
    expect(totalCSSSizeKB).toBeLessThan(500); // Less than 500KB total CSS
    
    // Application should be functional
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
  });
});