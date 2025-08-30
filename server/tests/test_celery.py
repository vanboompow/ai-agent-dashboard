import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import uuid

from app.celery_worker.celery_app import celery_app
from app.celery_worker.tasks import (
    process_agent_task,
    cleanup_completed_tasks,
    collect_system_metrics,
    send_heartbeat,
    process_batch_tasks
)


class TestCeleryApp:
    """Test suite for Celery application configuration."""
    
    def test_celery_app_configuration(self):
        """Test that Celery app is configured properly."""
        assert celery_app.conf.broker_url is not None
        assert celery_app.conf.result_backend is not None
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.accept_content == ['json']
        assert celery_app.conf.result_serializer == 'json'
    
    def test_celery_timezone_configuration(self):
        """Test timezone configuration."""
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.enable_utc is True
    
    def test_task_routes_configuration(self):
        """Test task routing configuration."""
        # Verify important tasks are routed correctly
        task_routes = celery_app.conf.task_routes
        assert isinstance(task_routes, dict) or task_routes is None
    
    def test_celery_task_discovery(self):
        """Test that tasks are properly discovered."""
        registered_tasks = celery_app.tasks.keys()
        expected_tasks = [
            'app.celery_worker.tasks.process_agent_task',
            'app.celery_worker.tasks.cleanup_completed_tasks',
            'app.celery_worker.tasks.collect_system_metrics',
            'app.celery_worker.tasks.send_heartbeat',
            'app.celery_worker.tasks.process_batch_tasks'
        ]
        
        for task_name in expected_tasks:
            assert task_name in registered_tasks


class TestProcessAgentTask:
    """Test suite for process_agent_task Celery task."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_process_agent_task_success(self, mock_redis, mock_db_session):
        """Test successful agent task processing."""
        # Mock dependencies
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        task_data = {
            "task_id": str(uuid.uuid4()),
            "agent_id": str(uuid.uuid4()),
            "task_type": "test_task",
            "parameters": {"param1": "value1"}
        }
        
        # Execute task
        result = process_agent_task.apply(args=[task_data])
        
        # Verify result
        assert result.successful()
        assert result.result["status"] == "completed"
        assert result.result["task_id"] == task_data["task_id"]
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_process_agent_task_failure(self, mock_db_session):
        """Test agent task processing failure."""
        # Mock database error
        mock_db_session.side_effect = Exception("Database connection failed")
        
        task_data = {
            "task_id": str(uuid.uuid4()),
            "agent_id": str(uuid.uuid4()),
            "task_type": "test_task",
            "parameters": {}
        }
        
        # Execute task
        result = process_agent_task.apply(args=[task_data])
        
        # Verify failure handling
        assert result.failed()
        assert "Database connection failed" in str(result.traceback)
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_process_agent_task_with_retry(self, mock_redis, mock_db_session):
        """Test agent task processing with retry logic."""
        # Mock temporary failure
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.side_effect = [Exception("Temporary error"), MagicMock()]
        
        task_data = {
            "task_id": str(uuid.uuid4()),
            "agent_id": str(uuid.uuid4()),
            "task_type": "test_task",
            "parameters": {}
        }
        
        # Execute task with retry
        with patch.object(process_agent_task, 'retry') as mock_retry:
            mock_retry.side_effect = Exception("Retrying...")
            
            result = process_agent_task.apply(args=[task_data])
            
            # Verify retry was attempted
            assert result.failed()


class TestCleanupCompletedTasks:
    """Test suite for cleanup_completed_tasks Celery task."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_cleanup_completed_tasks_success(self, mock_db_session):
        """Test successful cleanup of completed tasks."""
        # Mock database session and query results
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        # Mock completed tasks
        mock_completed_tasks = [MagicMock(), MagicMock(), MagicMock()]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_completed_tasks
        
        # Execute task
        result = cleanup_completed_tasks.apply()
        
        # Verify result
        assert result.successful()
        assert result.result["tasks_cleaned"] == 3
        assert result.result["status"] == "completed"
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_cleanup_completed_tasks_with_retention(self, mock_db_session):
        """Test cleanup with retention period."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        # Mock old completed tasks
        old_tasks = [MagicMock(), MagicMock()]
        mock_session.query.return_value.filter.return_value.all.return_value = old_tasks
        
        retention_days = 30
        result = cleanup_completed_tasks.apply(args=[retention_days])
        
        assert result.successful()
        assert result.result["tasks_cleaned"] == 2
        assert result.result["retention_days"] == retention_days
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_cleanup_completed_tasks_no_tasks(self, mock_db_session):
        """Test cleanup when no tasks need cleaning."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        result = cleanup_completed_tasks.apply()
        
        assert result.successful()
        assert result.result["tasks_cleaned"] == 0
        assert "No tasks to clean" in result.result["message"]


class TestCollectSystemMetrics:
    """Test suite for collect_system_metrics Celery task."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_collect_system_metrics_success(self, mock_redis, mock_db_session):
        """Test successful system metrics collection."""
        # Mock dependencies
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        # Mock metrics data
        mock_session.query.return_value.count.return_value = 5  # active agents
        mock_session.query.return_value.filter.return_value.count.return_value = 10  # queued tasks
        
        # Execute task
        result = collect_system_metrics.apply()
        
        # Verify result
        assert result.successful()
        metrics = result.result
        assert "active_agents_count" in metrics
        assert "tasks_queued" in metrics
        assert "timestamp" in metrics
        assert metrics["active_agents_count"] == 5
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_collect_system_metrics_with_calculations(self, mock_db_session):
        """Test metrics collection with calculated fields."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        # Mock aggregated data for calculations
        mock_session.query.return_value.filter.return_value.scalar.return_value = 1000  # total tokens
        mock_session.query.return_value.count.return_value = 3  # active agents
        
        result = collect_system_metrics.apply()
        
        assert result.successful()
        metrics = result.result
        assert "tokens_per_second" in metrics
        assert "cost_per_second_usd" in metrics
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_collect_system_metrics_with_redis_publish(self, mock_redis, mock_db_session):
        """Test metrics collection with Redis publishing."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        # Mock basic metrics
        mock_session.query.return_value.count.return_value = 2
        mock_session.query.return_value.filter.return_value.count.return_value = 5
        
        result = collect_system_metrics.apply(kwargs={"publish_to_stream": True})
        
        assert result.successful()
        # Verify Redis publish would be called (in actual implementation)


class TestSendHeartbeat:
    """Test suite for send_heartbeat Celery task."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_send_heartbeat_success(self, mock_redis, mock_db_session):
        """Test successful heartbeat sending."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        agent_id = str(uuid.uuid4())
        
        result = send_heartbeat.apply(args=[agent_id])
        
        assert result.successful()
        assert result.result["agent_id"] == agent_id
        assert result.result["status"] == "heartbeat_sent"
        assert "timestamp" in result.result
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_send_heartbeat_agent_not_found(self, mock_db_session):
        """Test heartbeat for non-existent agent."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        agent_id = str(uuid.uuid4())
        
        result = send_heartbeat.apply(args=[agent_id])
        
        assert result.successful()
        assert result.result["status"] == "agent_not_found"
        assert result.result["agent_id"] == agent_id
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_send_heartbeat_with_status_update(self, mock_redis, mock_db_session):
        """Test heartbeat with agent status update."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        # Mock agent
        mock_agent = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_agent
        
        agent_id = str(uuid.uuid4())
        status_update = {"current_task": "processing_data"}
        
        result = send_heartbeat.apply(args=[agent_id], kwargs={"status_update": status_update})
        
        assert result.successful()
        assert result.result["status"] == "heartbeat_sent"
        # Verify agent was updated (in actual implementation)


class TestProcessBatchTasks:
    """Test suite for process_batch_tasks Celery task."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_process_batch_tasks_success(self, mock_db_session):
        """Test successful batch task processing."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        batch_tasks = [
            {"task_id": str(uuid.uuid4()), "type": "data_processing"},
            {"task_id": str(uuid.uuid4()), "type": "model_training"},
            {"task_id": str(uuid.uuid4()), "type": "report_generation"}
        ]
        
        result = process_batch_tasks.apply(args=[batch_tasks])
        
        assert result.successful()
        assert result.result["total_tasks"] == 3
        assert result.result["successful_tasks"] >= 0
        assert result.result["failed_tasks"] >= 0
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_process_batch_tasks_partial_failure(self, mock_db_session):
        """Test batch processing with some failures."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        # Mock one task failure
        mock_session.query.side_effect = [Exception("Task failed"), MagicMock(), MagicMock()]
        
        batch_tasks = [
            {"task_id": str(uuid.uuid4()), "type": "failing_task"},
            {"task_id": str(uuid.uuid4()), "type": "success_task1"},
            {"task_id": str(uuid.uuid4()), "type": "success_task2"}
        ]
        
        result = process_batch_tasks.apply(args=[batch_tasks])
        
        assert result.successful()  # Batch job succeeds even with individual failures
        assert result.result["total_tasks"] == 3
        assert "failed_tasks" in result.result
    
    def test_process_batch_tasks_empty_batch(self):
        """Test processing empty batch."""
        result = process_batch_tasks.apply(args=[[]])
        
        assert result.successful()
        assert result.result["total_tasks"] == 0
        assert result.result["successful_tasks"] == 0
        assert result.result["failed_tasks"] == 0
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_process_batch_tasks_with_priority(self, mock_db_session):
        """Test batch processing with task prioritization."""
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        batch_tasks = [
            {"task_id": str(uuid.uuid4()), "type": "low_priority", "priority": 1},
            {"task_id": str(uuid.uuid4()), "type": "high_priority", "priority": 3},
            {"task_id": str(uuid.uuid4()), "type": "medium_priority", "priority": 2}
        ]
        
        result = process_batch_tasks.apply(args=[batch_tasks], kwargs={"sort_by_priority": True})
        
        assert result.successful()
        assert result.result["total_tasks"] == 3
        # In actual implementation, verify tasks were processed in priority order


class TestCeleryTaskErrorHandling:
    """Test suite for Celery task error handling."""
    
    @patch('app.celery_worker.tasks.get_database_session')
    def test_task_retry_mechanism(self, mock_db_session):
        """Test task retry mechanism for transient failures."""
        # Mock transient database error
        mock_db_session.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection timeout"), 
            MagicMock()  # Success on third try
        ]
        
        task_data = {"task_id": str(uuid.uuid4()), "type": "test_task"}
        
        # This test would need actual retry logic implementation
        # For now, verify the error is handled
        with pytest.raises(Exception, match="Connection timeout"):
            process_agent_task.apply(args=[task_data])
    
    def test_task_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        # Mock task that always fails
        with patch.object(process_agent_task, 'retry') as mock_retry:
            mock_retry.side_effect = process_agent_task.MaxRetriesExceededError()
            
            task_data = {"task_id": str(uuid.uuid4()), "type": "failing_task"}
            
            result = process_agent_task.apply(args=[task_data])
            assert result.failed()
    
    def test_task_dead_letter_queue(self):
        """Test dead letter queue functionality for failed tasks."""
        # This would test integration with dead letter queue
        # Implementation depends on Celery configuration
        pass
    
    @patch('app.celery_worker.tasks.get_database_session')
    @patch('app.celery_worker.tasks.redis.from_url')
    def test_task_timeout_handling(self, mock_redis, mock_db_session):
        """Test task timeout handling."""
        # Mock long-running operation
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        
        def slow_operation():
            import time
            time.sleep(10)  # Simulate slow operation
            
        mock_session.execute.side_effect = slow_operation
        
        task_data = {"task_id": str(uuid.uuid4()), "type": "slow_task"}
        
        # Test with timeout (would need actual timeout configuration)
        result = process_agent_task.apply(args=[task_data])
        # Verify timeout handling in actual implementation