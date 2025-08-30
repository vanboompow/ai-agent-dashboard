from celery import Celery
from kombu import Queue, Exchange
from ..config import settings
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    'ai_agent_dashboard',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.celery_worker.tasks']
)

# Configure task routing with multiple queues
default_exchange = Exchange('default', type='direct')
high_priority_exchange = Exchange('high_priority', type='direct')
background_exchange = Exchange('background', type='direct')

celery_app.conf.update(
    # Serialization and compression
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_compression='gzip',
    task_compression='gzip',
    
    # Time and timezone settings
    timezone='UTC',
    enable_utc=True,
    
    # Task tracking and timing
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    
    # Result backend settings
    result_backend_transport_options={
        'master_name': 'mymaster',
    },
    result_expires=7200,  # Results expire after 2 hours
    
    # Retry policies
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Queue definitions
    task_routes={
        'app.celery_worker.tasks.process_agent_task': {'queue': 'high_priority'},
        'app.celery_worker.tasks.task_orchestrator': {'queue': 'high_priority'},
        'app.celery_worker.tasks.heartbeat_check': {'queue': 'normal'},
        'app.celery_worker.tasks.collect_metrics': {'queue': 'normal'},
        'app.celery_worker.tasks.cleanup_completed': {'queue': 'background'},
        'app.celery_worker.tasks.broadcast_pause_all': {'queue': 'high_priority'},
        'app.celery_worker.tasks.broadcast_resume_all': {'queue': 'high_priority'},
    },
    
    # Queue configurations
    task_queues=[
        Queue('high_priority', 
              exchange=high_priority_exchange, 
              routing_key='high_priority',
              queue_arguments={'x-max-priority': 10}),
        Queue('normal', 
              exchange=default_exchange, 
              routing_key='normal',
              queue_arguments={'x-max-priority': 5}),
        Queue('background', 
              exchange=background_exchange, 
              routing_key='background',
              queue_arguments={'x-max-priority': 1}),
    ],
    
    # Default queue
    task_default_queue='normal',
    task_default_exchange='default',
    task_default_exchange_type='direct',
    task_default_routing_key='normal',
    
    # Worker settings
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'collect-metrics': {
            'task': 'app.celery_worker.tasks.collect_metrics',
            'schedule': 30.0,  # Every 30 seconds
        },
        'heartbeat-check': {
            'task': 'app.celery_worker.tasks.heartbeat_check',
            'schedule': 10.0,  # Every 10 seconds
        },
        'cleanup-completed-tasks': {
            'task': 'app.celery_worker.tasks.cleanup_completed',
            'schedule': 300.0,  # Every 5 minutes
        },
    },
    beat_schedule_filename='celerybeat-schedule',
)

# Error handling configuration
@celery_app.task(bind=True)
def task_failure_handler(self, task_id, error, traceback):
    """Handle task failures with detailed logging"""
    logger.error(f"Task {task_id} failed: {error}")
    logger.error(f"Traceback: {traceback}")
    
    # Publish failure event to Redis
    from .events import publish_event
    publish_event('task_failed', {
        'task_id': task_id,
        'error': str(error),
        'timestamp': self.request.utc
    })

# Success handler
@celery_app.task(bind=True)
def task_success_handler(self, retval, task_id, args, kwargs):
    """Handle successful task completion"""
    logger.info(f"Task {task_id} completed successfully")
    
    # Publish success event to Redis
    from .events import publish_event
    publish_event('task_completed', {
        'task_id': task_id,
        'result': retval,
        'timestamp': self.request.utc
    })