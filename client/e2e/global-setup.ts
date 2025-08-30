import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting E2E test setup...');
  
  // Launch browser for setup
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Wait for services to be available
    console.log('⏳ Waiting for backend API...');
    let backendReady = false;
    let attempts = 0;
    const maxAttempts = 30;
    
    while (!backendReady && attempts < maxAttempts) {
      try {
        const response = await page.request.get('http://localhost:8000/healthz');
        if (response.status() === 200) {
          backendReady = true;
          console.log('✅ Backend API is ready');
        }
      } catch (error) {
        attempts++;
        await page.waitForTimeout(2000);
        console.log(`⏳ Backend not ready, attempt ${attempts}/${maxAttempts}`);
      }
    }
    
    if (!backendReady) {
      throw new Error('Backend API failed to start within timeout');
    }
    
    console.log('⏳ Waiting for frontend...');
    let frontendReady = false;
    attempts = 0;
    
    while (!frontendReady && attempts < maxAttempts) {
      try {
        const response = await page.request.get('http://localhost:5173');
        if (response.status() === 200) {
          frontendReady = true;
          console.log('✅ Frontend is ready');
        }
      } catch (error) {
        attempts++;
        await page.waitForTimeout(2000);
        console.log(`⏳ Frontend not ready, attempt ${attempts}/${maxAttempts}`);
      }
    }
    
    if (!frontendReady) {
      throw new Error('Frontend failed to start within timeout');
    }
    
    // Seed test data if needed
    console.log('📦 Setting up test data...');
    
    // Create test agents
    try {
      await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: 'test_agent_1',
          hostname: 'test-host-1',
          current_status: 'idle'
        }
      });
      
      await page.request.post('http://localhost:8000/api/agents', {
        data: {
          agent_type: 'test_agent_2',
          hostname: 'test-host-2', 
          current_status: 'working'
        }
      });
    } catch (error) {
      console.log('⚠️ Failed to create test agents (may be expected):', error.message);
    }
    
    // Create test tasks
    try {
      await page.request.post('http://localhost:8000/api/tasks', {
        data: {
          description: 'E2E Test Task 1',
          sector: 'testing',
          task_type: 'e2e_test',
          priority: 'high'
        }
      });
      
      await page.request.post('http://localhost:8000/api/tasks', {
        data: {
          description: 'E2E Test Task 2',
          sector: 'testing',
          task_type: 'e2e_test',
          priority: 'medium'
        }
      });
    } catch (error) {
      console.log('⚠️ Failed to create test tasks (may be expected):', error.message);
    }
    
    console.log('✅ E2E test setup complete');
    
  } catch (error) {
    console.error('❌ E2E setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

export default globalSetup;