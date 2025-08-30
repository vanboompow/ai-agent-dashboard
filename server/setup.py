from setuptools import setup, find_packages

setup(
    name="ai-agent-dashboard-server",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.25.0",
        "celery>=5.3.4",
        "redis>=5.0.1",
        "sqlalchemy>=2.0.25",
        "alembic>=1.13.1",
        "psycopg2-binary>=2.9.9",
        "pydantic>=2.5.3",
    ],
)