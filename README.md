# 🧠 AI Agent Dashboard

Real-time monitoring and orchestration dashboard for distributed AI agents with radar-style visualization.

![Dashboard Preview](docs/dashboard-preview.png)

## ✨ Features

- 📡 **D3-based Radar View** - Real-time agent activity visualization
- 📋 **Interactive Task Queue** - AG Grid-powered task management
- 📊 **Live Metrics Dashboard** - Token usage, costs, and performance metrics
- 🕹️ **Global Control Panel** - System-wide throttling and control
- 🔄 **Real-time Updates** - Server-Sent Events (SSE) streaming

## 🧰 Tech Stack

- **Frontend**: React, TypeScript, D3.js, AG Grid, MobX, Chart.js
- **Backend**: FastAPI, Celery, Redis, PostgreSQL
- **Real-Time**: Server-Sent Events (SSE)
- **Container**: Docker & Docker Compose

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-agent-dashboard.git
cd ai-agent-dashboard

# Start the entire stack
docker-compose up --build

# Access the dashboard
open http://localhost:5173
```

### Manual Setup

#### Backend
```bash
cd server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd client
npm install
npm run dev
```

#### Required Services
- PostgreSQL (port 5432)
- Redis (port 6379)

## 🧪 Running Tests

```bash
# Frontend tests
cd client
npm run test

# Backend tests
cd server
pytest

# Full test suite
npm test  # from root directory
```

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │  Radar   │ │Task Queue│ │ Metrics  │ │Control │ │
│  │  (D3.js) │ │(AG Grid) │ │(Chart.js)│ │ Panel  │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                      │                               │
│                 MobX Store                           │
│                      │                               │
│                 SSE Client                           │
└──────────────────────┬───────────────────────────────┘
                       │ Server-Sent Events
┌──────────────────────┴───────────────────────────────┐
│                  Backend (FastAPI)                    │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   REST API   │  │ SSE Endpoint │  │   Celery   │ │
│  └──────────────┘  └──────────────┘  │   Worker   │ │
│         │                 │           └────────────┘ │
│  ┌──────┴─────────────────┴────────────────────┐    │
│  │            Redis Pub/Sub                     │    │
│  └──────────────────────────────────────────────┘    │
│                      │                               │
│  ┌───────────────────┴────────────────────────┐     │
│  │           PostgreSQL Database               │     │
│  └─────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────┘
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the server directory:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_dashboard
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Frontend Configuration

Update `client/src/config.ts`:

```typescript
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const SSE_ENDPOINT = `${API_BASE_URL}/api/stream`;
```

## 📚 API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- Inspired by military radar systems and command centers
- Built with modern web technologies
- Designed for scalability and real-time performance