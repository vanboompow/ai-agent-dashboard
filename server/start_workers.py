#!/usr/bin/env python3
"""
Celery Worker Startup Script

This script starts Celery workers with proper configuration for the AI Agent Dashboard.
It handles multiple worker types, monitoring, and graceful shutdown.
"""

import os
import sys
import signal
import subprocess
import time
import logging
from multiprocessing import Process
from typing import List, Dict, Any

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CeleryWorkerManager:
    """
    Manages multiple Celery workers with different configurations
    """
    
    def __init__(self):
        """Initialize the worker manager"""
        self.processes = []
        self.monitoring_process = None
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        self.stop_all_workers()
    
    def start_worker(self, worker_name: str, queues: List[str], 
                     concurrency: int = 2, pool: str = "threads") -> subprocess.Popen:
        """
        Start a single Celery worker
        
        Args:
            worker_name: Unique name for the worker
            queues: List of queues this worker should process
            concurrency: Number of concurrent processes/threads
            pool: Pool type (threads, processes, solo)
        
        Returns:
            Started subprocess
        """
        cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.celery_worker.celery_app",
            "worker",
            "--loglevel=info",
            f"--hostname={worker_name}@%h",
            f"--queues={','.join(queues)}",
            f"--concurrency={concurrency}",
            f"--pool={pool}",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat"
        ]
        
        logger.info(f"Starting worker '{worker_name}' for queues {queues}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append({
                'name': worker_name,
                'process': process,
                'queues': queues,
                'cmd': cmd
            })
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start worker '{worker_name}': {e}")
            raise
    
    def start_beat_scheduler(self) -> subprocess.Popen:
        """Start Celery Beat scheduler for periodic tasks"""
        cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.celery_worker.celery_app",
            "beat",
            "--loglevel=info",
            "--pidfile=/tmp/celerybeat.pid",
            "--schedule=/tmp/celerybeat-schedule"
        ]
        
        logger.info("Starting Celery Beat scheduler")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append({
                'name': 'beat-scheduler',
                'process': process,
                'queues': ['scheduler'],
                'cmd': cmd
            })
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start beat scheduler: {e}")
            raise
    
    def start_flower_monitoring(self, port: int = 5555) -> subprocess.Popen:
        """Start Flower monitoring web interface"""
        cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.celery_worker.celery_app",
            "flower",
            f"--port={port}",
            "--basic_auth=admin:admin123"
        ]
        
        logger.info(f"Starting Flower monitoring on port {port}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.monitoring_process = process
            return process
            
        except Exception as e:
            logger.error(f"Failed to start Flower monitoring: {e}")
            raise
    
    def start_all_workers(self, include_monitoring: bool = True):
        """Start all worker types with optimal configuration"""
        
        logger.info("Starting AI Agent Dashboard Celery workers...")
        
        # Start high-priority worker (single-threaded for reliability)
        self.start_worker(
            worker_name="high-priority-worker",
            queues=["high_priority"],
            concurrency=1,
            pool="solo"
        )
        
        # Start normal workers (multi-threaded for throughput)
        self.start_worker(
            worker_name="normal-worker-1",
            queues=["normal"],
            concurrency=4,
            pool="threads"
        )
        
        self.start_worker(
            worker_name="normal-worker-2", 
            queues=["normal"],
            concurrency=4,
            pool="threads"
        )
        
        # Start background worker (lower priority tasks)
        self.start_worker(
            worker_name="background-worker",
            queues=["background"],
            concurrency=2,
            pool="threads"
        )
        
        # Start Beat scheduler for periodic tasks
        self.start_beat_scheduler()
        
        # Start monitoring if requested
        if include_monitoring:
            try:
                self.start_flower_monitoring()
            except Exception as e:
                logger.warning(f"Failed to start monitoring (continuing without it): {e}")
        
        logger.info(f"Started {len(self.processes)} worker processes")
        
        # Log worker configuration
        for worker_info in self.processes:
            logger.info(f"Worker '{worker_info['name']}' processing queues: {worker_info['queues']}")
    
    def check_worker_health(self):
        """Check health of all workers and restart if needed"""
        for worker_info in self.processes[:]:  # Copy list to allow modification
            process = worker_info['process']
            
            if process.poll() is not None:
                # Process has terminated
                return_code = process.returncode
                logger.error(f"Worker '{worker_info['name']}' terminated with code {return_code}")
                
                # Remove from active processes
                self.processes.remove(worker_info)
                
                # Restart worker if we're still running
                if self.running:
                    logger.info(f"Restarting worker '{worker_info['name']}'...")
                    try:
                        if worker_info['name'] == 'beat-scheduler':
                            self.start_beat_scheduler()
                        else:
                            # Extract parameters from command
                            queues = worker_info['queues']
                            concurrency = 2  # Default
                            pool = "threads"  # Default
                            
                            self.start_worker(
                                worker_name=worker_info['name'],
                                queues=queues,
                                concurrency=concurrency,
                                pool=pool
                            )
                    except Exception as e:
                        logger.error(f"Failed to restart worker '{worker_info['name']}': {e}")
    
    def stop_all_workers(self):
        """Stop all workers gracefully"""
        logger.info("Stopping all workers...")
        
        # Stop monitoring first
        if self.monitoring_process:
            try:
                self.monitoring_process.terminate()
                self.monitoring_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.monitoring_process.kill()
            except Exception as e:
                logger.error(f"Error stopping monitoring: {e}")
        
        # Stop all workers
        for worker_info in self.processes:
            try:
                process = worker_info['process']
                logger.info(f"Stopping worker '{worker_info['name']}'...")
                
                # Send SIGTERM for graceful shutdown
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=30)
                    logger.info(f"Worker '{worker_info['name']}' stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning(f"Force killing worker '{worker_info['name']}'")
                    process.kill()
                    process.wait()
                    
            except Exception as e:
                logger.error(f"Error stopping worker '{worker_info['name']}': {e}")
        
        self.processes.clear()
        logger.info("All workers stopped")
    
    def monitor_workers(self):
        """Main monitoring loop"""
        logger.info("Starting worker monitoring loop...")
        
        while self.running:
            try:
                # Check worker health
                self.check_worker_health()
                
                # Log status
                active_workers = len([w for w in self.processes if w['process'].poll() is None])
                if active_workers > 0:
                    logger.debug(f"Monitoring: {active_workers} active workers")
                
                # Sleep before next check
                time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)  # Wait before retrying
    
    def run(self, include_monitoring: bool = True, daemon: bool = False):
        """
        Run the worker manager
        
        Args:
            include_monitoring: Whether to start Flower monitoring
            daemon: Whether to run in daemon mode (return immediately)
        """
        try:
            # Start all workers
            self.start_all_workers(include_monitoring=include_monitoring)
            
            if daemon:
                logger.info("Started in daemon mode")
                return
            
            # Start monitoring loop
            self.monitor_workers()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.stop_all_workers()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Agent Dashboard Celery Worker Manager")
    parser.add_argument(
        "--no-monitoring", 
        action="store_true", 
        help="Don't start Flower monitoring interface"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode (start workers and exit)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Check environment
    if not os.getenv('CELERY_BROKER_URL') and not os.getenv('REDIS_URL'):
        logger.warning("Neither CELERY_BROKER_URL nor REDIS_URL environment variables set")
        logger.info("Using default Redis connection: redis://localhost:6379/0")
    
    # Start worker manager
    manager = CeleryWorkerManager()
    manager.run(
        include_monitoring=not args.no_monitoring,
        daemon=args.daemon
    )


if __name__ == "__main__":
    main()