#!/bin/bash

# PR Validation System Setup Script
# This script sets up the development environment for the PR Validation System

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running from project root
if [ ! -f "requirements.txt" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_info "Starting PR Validation System setup..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    print_error "Python 3.10 or higher is required. Current version: $PYTHON_VERSION"
    exit 1
fi

print_success "Python version check passed: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
print_info "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
print_info "Creating project directories..."
mkdir -p logs data cache validation_reports

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_info "Creating .env file from .env.example..."
        cp .env.example .env
        print_warning "Please update .env file with your actual configuration values"
    else
        print_error ".env.example file not found"
        exit 1
    fi
else
    print_info ".env file already exists"
fi

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    print_info "Installing pre-commit hooks..."
    pre-commit install
    print_success "Pre-commit hooks installed"
else
    print_warning "pre-commit not found. Install it with: pip install pre-commit"
fi

# Check Docker installation
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,$//')
    print_success "Docker found: version $DOCKER_VERSION"

    # Check Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,$//')
        print_success "Docker Compose found: version $COMPOSE_VERSION"
    else
        print_warning "Docker Compose not found. Install it for container deployment"
    fi
else
    print_warning "Docker not found. Install Docker for container deployment"
fi

# Check Azure CLI
if command -v az &> /dev/null; then
    AZ_VERSION=$(az --version | head -n 1 | awk '{print $2}')
    print_success "Azure CLI found: version $AZ_VERSION"
else
    print_warning "Azure CLI not found. Install it for Azure integration"
fi

# Validate configuration
print_info "Validating configuration..."

# Check required environment variables
REQUIRED_VARS=("API_KEY" "AZURE_DEVOPS_PAT" "OPENAI_API_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=your-" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    print_warning "The following required environment variables are not set in .env:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
fi

# Create systemd service file (optional)
if [ -d "/etc/systemd/system" ] && [ "$EUID" -eq 0 ]; then
    print_info "Creating systemd service file..."
    cat > /etc/systemd/system/pr-validation.service << EOF
[Unit]
Description=PR Validation System API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$(pwd)/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    print_success "Systemd service file created"
fi

# Run initial tests
print_info "Running basic tests..."
python -m pytest tests/unit/test_models.py -v || print_warning "Some tests failed. Please check the test output."

# Generate initial documentation
if command -v mkdocs &> /dev/null; then
    print_info "Building documentation..."
    mkdocs build
    print_success "Documentation built in site/ directory"
fi

print_success "Setup completed successfully!"
print_info ""
print_info "Next steps:"
print_info "1. Update the .env file with your configuration"
print_info "2. Run 'source venv/bin/activate' to activate the virtual environment"
print_info "3. Run 'uvicorn api.main:app --reload' to start the development server"
print_info "4. Visit http://localhost:8000/api/docs for API documentation"
print_info ""
print_info "For production deployment, run: ./scripts/deploy.sh"