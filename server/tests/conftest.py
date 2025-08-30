import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.main import app
from app.models.base import Base
from app.models.agent import Agent, AgentStatus
from app.models.task import Task, TaskPriority, TaskStatus, TaskLog, SystemMetric
from app.config import Settings


# Test database settings
TEST_DATABASE_URL = "sqlite:///./test.db"


class TestSettings(Settings):
    database_url: str = "sqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/1"
    testing: bool = True
    
    class Config:
        env_file = None


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Test settings fixture."""
    return TestSettings()


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
async def redis_client():
    """Create a test Redis client."""
    redis_client = AsyncMock(spec=redis.Redis)
    # Mock common Redis operations
    redis_client.publish = AsyncMock(return_value=1)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.close = AsyncMock()
    yield redis_client


@pytest.fixture(scope="function")
def mock_celery():
    """Mock Celery for testing."""
    celery_mock = MagicMock()
    celery_mock.send_task = MagicMock(return_value=MagicMock(id="test-task-id"))
    return celery_mock


@pytest.fixture(scope="function")
async def test_app(redis_client, test_settings) -> FastAPI:
    """Create a test FastAPI app."""
    test_app = app
    test_app.state.redis = redis_client
    test_app.state.settings = test_settings
    return test_app


@pytest.fixture(scope="function")
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver"
    ) as ac:
        yield ac


# Sample data fixtures
@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing."""
    return {
        "agent_type": "test_agent",
        "hostname": "test-host",
        "current_status": AgentStatus.idle
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "description": "Test task description",
        "sector": "test_sector",
        "task_type": "test_type",
        "token_usage": 1000,
        "estimated_cost_usd": 0.002
    }


@pytest.fixture
def sample_agent(db_session, sample_agent_data):
    """Create a sample agent for testing."""
    agent = Agent(**sample_agent_data)
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def sample_task(db_session, sample_task_data):
    """Create a sample task for testing."""
    task = Task(**sample_task_data)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# Mock HTTP responses
@pytest.fixture
def mock_successful_response():
    """Mock successful HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    return mock_response


@pytest.fixture
def mock_error_response():
    """Mock error HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": "Internal server error"}
    return mock_response


# Utility functions
def create_test_agent(db_session, **kwargs) -> Agent:
    """Utility to create test agents with custom data."""
    default_data = {
        "agent_type": "test_agent",
        "hostname": "test-host",
        "current_status": AgentStatus.idle
    }
    default_data.update(kwargs)
    agent = Agent(**default_data)
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def create_test_task(db_session, **kwargs) -> Task:
    """Utility to create test tasks with custom data."""
    default_data = {
        "description": "Test task",
        "sector": "test",
        "task_type": "test_type",
        "token_usage": 100,
        "estimated_cost_usd": 0.001
    }
    default_data.update(kwargs)
    task = Task(**default_data)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task