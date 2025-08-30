import { chromium, FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Starting E2E test cleanup...');
  
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Clean up test data
    console.log('📦 Cleaning up test data...');
    
    // Clean up test agents and tasks
    try {
      // Get all test agents
      const agentsResponse = await page.request.get('http://localhost:8000/api/agents');
      if (agentsResponse.ok()) {
        const agents = await agentsResponse.json();
        for (const agent of agents) {
          if (agent.agent_type?.includes('test_')) {
            await page.request.delete(`http://localhost:8000/api/agents/${agent.agent_id}`);
          }
        }
      }
      
      // Get all test tasks
      const tasksResponse = await page.request.get('http://localhost:8000/api/tasks');
      if (tasksResponse.ok()) {
        const tasks = await tasksResponse.json();
        for (const task of tasks) {
          if (task.sector === 'testing' || task.task_type === 'e2e_test') {
            await page.request.delete(`http://localhost:8000/api/tasks/${task.task_id}`);
          }
        }
      }
      
    } catch (error) {
      console.log('⚠️ Failed to cleanup test data (may be expected):', error.message);
    }
    
    console.log('✅ E2E test cleanup complete');
    
  } catch (error) {
    console.error('❌ E2E cleanup failed:', error);
    // Don't throw here, as cleanup failures shouldn't fail the test suite
  } finally {
    await browser.close();
  }
}

export default globalTeardown;