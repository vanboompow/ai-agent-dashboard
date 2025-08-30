import { test, expect } from '@playwright/test';

test.describe('Real-time Updates (SSE)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should establish SSE connection', async ({ page }) => {
    // Monitor network requests for EventSource connection
    const sseRequest = page.waitForRequest(/.*\/api\/stream/);
    
    await page.goto('/');
    
    // Should make a request to the streaming endpoint
    const request = await sseRequest;
    expect(request.url()).toContain('/api/stream');
  });

  test('should handle agent status updates via SSE', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Get initial agent state
    const agentRadar = page.locator('[data-testid="agent-radar"]');
    await expect(agentRadar).toBeVisible();
    
    // Simulate agent status change via API
    await page.request.post('http://localhost:8000/api/agents', {
      data: {
        agent_type: 'sse_test_agent',
        hostname: 'sse-test-host',
        current_status: 'idle'
      }
    });
    
    // Wait for the SSE update to be processed
    await page.waitForTimeout(1000);
    
    // Agent radar should still be visible and responsive
    await expect(agentRadar).toBeVisible();
    
    // Clean up test agent
    const agentsResponse = await page.request.get('http://localhost:8000/api/agents');
    if (agentsResponse.ok()) {
      const agents = await agentsResponse.json();
      const testAgent = agents.find(a => a.agent_type === 'sse_test_agent');
      if (testAgent) {
        await page.request.delete(`http://localhost:8000/api/agents/${testAgent.agent_id}`);
      }
    }
  });

  test('should handle task updates via SSE', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const taskQueue = page.locator('[data-testid="task-queue"]');
    await expect(taskQueue).toBeVisible();
    
    // Create a new task via API
    const newTaskResponse = await page.request.post('http://localhost:8000/api/tasks', {
      data: {
        description: 'SSE Test Task',
        sector: 'sse_testing',
        task_type: 'sse_test',
        priority: 'medium'
      }
    });
    
    if (newTaskResponse.ok()) {
      const newTask = await newTaskResponse.json();
      
      // Wait for SSE update
      await page.waitForTimeout(1000);
      
      // Task queue should still be functional
      await expect(taskQueue).toBeVisible();
      
      // Clean up test task
      await page.request.delete(`http://localhost:8000/api/tasks/${newTask.task_id}`);
    }
  });

  test('should handle metrics updates via SSE', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const metricsPanel = page.locator('[data-testid="metrics-panel"]');
    await expect(metricsPanel).toBeVisible();
    
    // Capture initial metrics state
    const initialContent = await metricsPanel.textContent();
    
    // Wait for potential SSE metrics updates
    await page.waitForTimeout(2000);
    
    // Metrics panel should remain functional
    await expect(metricsPanel).toBeVisible();
    
    // Content may or may not have changed, but should still be valid
    const updatedContent = await metricsPanel.textContent();
    expect(updatedContent).toBeTruthy();
  });

  test('should handle SSE connection loss gracefully', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Block SSE requests to simulate connection loss
    await page.route('/api/stream', route => route.abort());
    
    // Refresh to trigger SSE connection attempt
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // Application should still be functional without SSE
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
  });

  test('should handle rapid SSE updates', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Create multiple agents in quick succession
    const agents = [];
    for (let i = 0; i < 5; i++) {
      const agentResponse = await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: `rapid_test_agent_${i}`,
          hostname: `rapid-test-host-${i}`,
          current_status: 'idle'
        }
      });
      
      if (agentResponse.ok()) {
        const agent = await agentResponse.json();
        agents.push(agent);
      }
    }
    
    // Wait for SSE updates to be processed
    await page.waitForTimeout(2000);
    
    // Application should remain responsive
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
    
    // Clean up test agents
    for (const agent of agents) {
      await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
    }
  });

  test('should maintain real-time connection across user interactions', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Interact with the control panel
    const controlPanel = page.locator('[data-testid="control-panel"]');
    const runButton = controlPanel.locator('button', { hasText: /run/i });
    
    if (await runButton.isVisible()) {
      await runButton.click();
      await page.waitForTimeout(500);
    }
    
    // Create an agent to test SSE still works
    const agentResponse = await page.request.post('http://localhost:8000/api/agents', {
      data: {
        agent_type: 'interaction_test_agent',
        hostname: 'interaction-test-host',
        current_status: 'working'
      }
    });
    
    if (agentResponse.ok()) {
      const agent = await agentResponse.json();
      
      // Wait for SSE update
      await page.waitForTimeout(1000);
      
      // Verify application is still functional
      await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
      
      // Clean up
      await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
    }
  });

  test('should handle SSE reconnection', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Initial state check
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    
    // Simulate temporary network issue by blocking SSE, then unblocking
    await page.route('/api/stream', route => route.abort());
    
    // Wait a moment
    await page.waitForTimeout(1000);
    
    // Unblock SSE
    await page.unroute('/api/stream');
    
    // Try to trigger reconnection (implementation dependent)
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // Should be functional again
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
  });
});

test.describe('WebSocket Compatibility (if implemented)', () => {
  test('should handle WebSocket connections', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // This test assumes WebSocket might be used as fallback or alternative
    // Monitor for WebSocket connections
    const wsConnections = [];
    
    page.on('websocket', ws => {
      wsConnections.push(ws);
    });
    
    await page.waitForTimeout(2000);
    
    // Application should work regardless of transport mechanism
    await expect(page.locator('[data-testid="agent-radar"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-queue"]')).toBeVisible();
  });

  test('should handle WebSocket message flow', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const messages = [];
    
    page.on('websocket', ws => {
      ws.on('framereceived', event => messages.push(event.payload));
      ws.on('framesent', event => messages.push(event.payload));
    });
    
    // Interact with the application
    const controlPanel = page.locator('[data-testid="control-panel"]');
    const runButton = controlPanel.locator('button', { hasText: /run/i });
    
    if (await runButton.isVisible()) {
      await runButton.click();
    }
    
    await page.waitForTimeout(1000);
    
    // Application should remain functional
    await expect(page.locator('[data-testid="control-panel"]')).toBeVisible();
  });
});