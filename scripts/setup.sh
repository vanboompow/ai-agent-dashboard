#!/bin/bash
# AI Agent Dashboard - Development Environment Setup Script
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="3.11"
NODE_VERSION="18"
PROJECT_NAME="ai-agent-dashboard"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

install_python_deps() {
    log_info "Installing Python dependencies..."
    
    if ! check_command python3; then
        log_error "Python 3 is not installed. Please install Python ${PYTHON_VERSION} first."
        exit 1
    fi
    
    # Check Python version
    python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    if [[ "$python_version" < "$PYTHON_VERSION" ]]; then
        log_warning "Python version $python_version detected. Recommended: $PYTHON_VERSION+"
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "server/.venv" ]]; then
        log_info "Creating Python virtual environment..."
        cd server
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip
        cd ..
    fi
    
    # Install requirements
    cd server
    source .venv/bin/activate
    pip install -r requirements.txt
    cd ..
    
    log_success "Python dependencies installed"
}

install_node_deps() {
    log_info "Installing Node.js dependencies..."
    
    if ! check_command node; then
        log_error "Node.js is not installed. Please install Node.js ${NODE_VERSION}+ first."
        exit 1
    fi
    
    # Check Node version
    node_version=$(node -v | sed 's/v//')
    node_major=$(echo "$node_version" | cut -d. -f1)
    if [[ "$node_major" -lt "${NODE_VERSION}" ]]; then
        log_warning "Node.js version $node_version detected. Recommended: ${NODE_VERSION}+"
    fi
    
    # Install frontend dependencies
    cd client
    npm install
    cd ..
    
    log_success "Node.js dependencies installed"
}

install_development_tools() {
    log_info "Installing development tools..."
    
    # Install pre-commit if available
    if check_command pip3; then
        pip3 install pre-commit
        pre-commit install --install-hooks
        pre-commit install --hook-type commit-msg
        log_success "Pre-commit hooks installed"
    else
        log_warning "pip3 not available, skipping pre-commit installation"
    fi
    
    # Install Playwright browsers
    if check_command npx; then
        cd client
        npx playwright install --with-deps
        cd ..
        log_success "Playwright browsers installed"
    else
        log_warning "npx not available, skipping Playwright installation"
    fi
}

setup_database() {
    log_info "Setting up database..."
    
    if ! check_command docker; then
        log_warning "Docker not available, skipping database setup"
        return 0
    fi
    
    # Start PostgreSQL container
    docker run --name ${PROJECT_NAME}-postgres -d \
        -e POSTGRES_DB=ai_dashboard \
        -e POSTGRES_USER=aiagent \
        -e POSTGRES_PASSWORD=aiagent123 \
        -p 5432:5432 \
        postgres:14-alpine || docker start ${PROJECT_NAME}-postgres
    
    # Start Redis container
    docker run --name ${PROJECT_NAME}-redis -d \
        -p 6379:6379 \
        redis:7-alpine || docker start ${PROJECT_NAME}-redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    cd server
    if [[ -d ".venv" ]]; then
        source .venv/bin/activate
    fi
    
    # Check if alembic is available and run migrations
    if check_command alembic; then
        alembic upgrade head
        log_success "Database migrations completed"
    else
        log_warning "Alembic not available, skipping migrations"
    fi
    
    cd ..
    
    log_success "Database setup completed"
}

setup_environment_files() {
    log_info "Setting up environment files..."
    
    # Backend environment
    if [[ ! -f "server/.env" ]]; then
        cat > server/.env << EOF
# Development environment variables
DATABASE_URL=postgresql://aiagent:aiagent123@localhost:5432/ai_dashboard
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
ENVIRONMENT=development
DEBUG=true
TESTING=false

# Optional integrations
# SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
# OPENAI_API_KEY=your-openai-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key
EOF
        log_success "Backend .env file created"
    else
        log_info "Backend .env file already exists"
    fi
    
    # Frontend environment
    if [[ ! -f "client/.env.local" ]]; then
        cat > client/.env.local << EOF
# Development environment variables
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENVIRONMENT=development
EOF
        log_success "Frontend .env.local file created"
    else
        log_info "Frontend .env.local file already exists"
    fi
}

run_health_checks() {
    log_info "Running health checks..."
    
    # Check if services are running
    if check_command curl; then
        # Check if database is accessible (if Docker is running)
        if check_command docker && docker ps | grep -q "${PROJECT_NAME}-postgres"; then
            log_success "PostgreSQL container is running"
        else
            log_warning "PostgreSQL container is not running"
        fi
        
        if check_command docker && docker ps | grep -q "${PROJECT_NAME}-redis"; then
            log_success "Redis container is running"
        else
            log_warning "Redis container is not running"
        fi
    fi
    
    # Verify Python environment
    if [[ -f "server/.venv/bin/activate" ]]; then
        cd server
        source .venv/bin/activate
        if python -c "import fastapi, uvicorn, sqlalchemy, redis" 2>/dev/null; then
            log_success "Python environment is working"
        else
            log_warning "Some Python dependencies may be missing"
        fi
        cd ..
    fi
    
    # Verify Node environment
    cd client
    if npm list --depth=0 &>/dev/null; then
        log_success "Node.js environment is working"
    else
        log_warning "Some Node.js dependencies may be missing"
    fi
    cd ..
}

print_usage() {
    cat << EOF
${GREEN}AI Agent Dashboard - Development Setup Complete!${NC}

${BLUE}Quick Start Commands:${NC}
  make dev                 # Start all development servers
  make test                # Run all tests
  make lint                # Run all linters
  make docker-up           # Start with Docker Compose

${BLUE}Individual Services:${NC}
  make dev-backend         # Start backend only
  make dev-frontend        # Start frontend only
  make dev-postgres        # Start PostgreSQL
  make dev-redis           # Start Redis

${BLUE}Testing:${NC}
  make test-backend        # Backend tests
  make test-frontend       # Frontend tests  
  make test-e2e           # End-to-end tests

${BLUE}Useful Commands:${NC}
  make help               # Show all available commands
  make health             # Check service health
  make logs               # Show application logs
  make clean              # Clean temporary files

${BLUE}URLs:${NC}
  Frontend:  http://localhost:5173
  Backend:   http://localhost:8000
  API Docs:  http://localhost:8000/docs
  Grafana:   http://localhost:3000
  Prometheus: http://localhost:9090

${YELLOW}Next Steps:${NC}
1. Review the .env files and update API keys if needed
2. Run 'make dev' to start the development servers
3. Visit http://localhost:5173 to see the application
4. Check out the API documentation at http://localhost:8000/docs

${PURPLE}For more help, run 'make help' or check the README.md${NC}
EOF
}

main() {
    echo -e "${CYAN}"
    cat << "EOF"
    ___    ____   ___                  __   
   /   |  /  _/  /   | ____ ____  ____/ /_  
  / /| |  / /   / /| |/ __ `/ _ \/ __  / __/ 
 / ___ |_/ /   / ___ / /_/ /  __/ /_/ / /_   
/_/  |_/___/  /_/  |_\__, /\___/\__,_/\__/   
                    /____/                   
    ____            __    __                         __
   / __ \____ ______/ /_  / /_  ____  ____ __________/ /
  / / / / __ `/ ___/ __ \/ __ \/ __ \/ __ `/ ___/ __  / 
 / /_/ / /_/ (__  ) / / / /_/ / /_/ / /_/ / /  / /_/ /  
/_____/\__,_/____/_/ /_/_.___/\____/\__,_/_/   \__,_/   
                                                        
EOF
    echo -e "${NC}"
    
    log_info "Starting AI Agent Dashboard development environment setup..."
    
    # Check if we're in the right directory
    if [[ ! -f "Makefile" ]] || [[ ! -d "server" ]] || [[ ! -d "client" ]]; then
        log_error "Please run this script from the project root directory"
        exit 1
    fi
    
    # Run setup steps
    install_python_deps
    install_node_deps
    install_development_tools
    setup_environment_files
    setup_database
    run_health_checks
    
    log_success "Setup completed successfully!"
    print_usage
}

# Handle script arguments
case "${1:-setup}" in
    "setup"|"")
        main
        ;;
    "python"|"backend")
        install_python_deps
        ;;
    "node"|"frontend")
        install_node_deps
        ;;
    "tools")
        install_development_tools
        ;;
    "database"|"db")
        setup_database
        ;;
    "env")
        setup_environment_files
        ;;
    "health")
        run_health_checks
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [setup|python|node|tools|database|env|health|help]"
        echo ""
        echo "Commands:"
        echo "  setup     - Run complete setup (default)"
        echo "  python    - Install Python dependencies only"
        echo "  node      - Install Node.js dependencies only"
        echo "  tools     - Install development tools only"
        echo "  database  - Setup database only"
        echo "  env       - Setup environment files only"
        echo "  health    - Run health checks only"
        echo "  help      - Show this help message"
        ;;
    *)
        log_error "Unknown command: $1"
        log_info "Use '$0 help' to see available commands"
        exit 1
        ;;
esac