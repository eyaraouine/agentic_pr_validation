#!/bin/bash

# PR Validation System Deployment Script
# This script deploys the PR Validation System to production

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_TYPE="${1:-docker}" # docker, kubernetes, azure
ENVIRONMENT="${2:-production}"
REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_NAME="${IMAGE_NAME:-pr-validation-system}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NAMESPACE="${K8S_NAMESPACE:-pr-validation}"

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

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if running from project root
    if [ ! -f "requirements.txt" ]; then
        print_error "Please run this script from the project root directory"
        exit 1
    fi

    # Check for .env file
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create it from .env.example"
        exit 1
    fi

    # Check deployment type specific requirements
    case $DEPLOYMENT_TYPE in
        docker)
            if ! command -v docker &> /dev/null; then
                print_error "Docker is required for Docker deployment"
                exit 1
            fi
            if ! command -v docker-compose &> /dev/null; then
                print_error "Docker Compose is required for Docker deployment"
                exit 1
            fi
            ;;
        kubernetes)
            if ! command -v kubectl &> /dev/null; then
                print_error "kubectl is required for Kubernetes deployment"
                exit 1
            fi
            ;;
        azure)
            if ! command -v az &> /dev/null; then
                print_error "Azure CLI is required for Azure deployment"
                exit 1
            fi
            ;;
        *)
            print_error "Unknown deployment type: $DEPLOYMENT_TYPE"
            print_info "Usage: $0 [docker|kubernetes|azure] [environment]"
            exit 1
            ;;
    esac

    print_success "Prerequisites check passed"
}

# Build Docker image
build_docker_image() {
    print_info "Building Docker image..."

    # Build image
    docker build -f docker/Dockerfile -t ${IMAGE_NAME}:${IMAGE_TAG} .

    # Tag with registry if provided
    if [ -n "$REGISTRY" ]; then
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
        print_success "Docker image built and tagged: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    else
        print_success "Docker image built: ${IMAGE_NAME}:${IMAGE_TAG}"
    fi
}

# Push Docker image
push_docker_image() {
    if [ -n "$REGISTRY" ]; then
        print_info "Pushing Docker image to registry..."
        docker push ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
        print_success "Docker image pushed to registry"
    else
        print_warning "No registry specified, skipping push"
    fi
}

# Deploy with Docker Compose
deploy_docker() {
    print_info "Deploying with Docker Compose..."

    # Create docker-compose override for production
    cat > docker/docker-compose.override.yml << EOF
version: '3.8'

services:
  api:
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
    restart: always

  nginx:
    restart: always

  db:
    restart: always

  redis:
    restart: always
EOF

    # Deploy
    cd docker
    docker-compose up -d
    cd ..

    print_success "Docker deployment completed"
    print_info "Services are starting up..."

    # Wait for services
    sleep 10

    # Check health
    if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
        print_success "API is healthy"
    else
        print_error "API health check failed"
    fi
}

# Deploy to Kubernetes
deploy_kubernetes() {
    print_info "Deploying to Kubernetes..."

    # Check if namespace exists
    if ! kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
        print_info "Creating namespace ${NAMESPACE}..."
        kubectl create namespace ${NAMESPACE}
    fi

    # Create secrets from .env
    print_info "Creating Kubernetes secrets..."
    kubectl create secret generic pr-validation-secrets \
        --from-env-file=.env \
        --namespace=${NAMESPACE} \
        --dry-run=client -o yaml | kubectl apply -f -

    # Apply Kubernetes manifests
    print_info "Applying Kubernetes manifests..."
    kubectl apply -f k8s/ -n ${NAMESPACE}

    # Wait for deployment
    print_info "Waiting for deployment to be ready..."
    kubectl rollout status deployment/pr-validation-api -n ${NAMESPACE}

    print_success "Kubernetes deployment completed"

    # Get service endpoint
    ENDPOINT=$(kubectl get service pr-validation-api -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$ENDPOINT" ]; then
        print_info "Service endpoint: http://${ENDPOINT}:8000"
    else
        print_info "Service is using ClusterIP. Use kubectl port-forward to access."
    fi
}

# Deploy to Azure
deploy_azure() {
    print_info "Deploying to Azure..."

    # Check Azure login
    if ! az account show > /dev/null 2>&1; then
        print_error "Please login to Azure: az login"
        exit 1
    fi

    # Set variables
    RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-pr-validation-rg}"
    LOCATION="${AZURE_LOCATION:-eastus}"
    APP_NAME="${AZURE_APP_NAME:-pr-validation-api}"

    # Create resource group
    print_info "Creating resource group..."
    az group create --name ${RESOURCE_GROUP} --location ${LOCATION}

    # Create App Service plan
    print_info "Creating App Service plan..."
    az appservice plan create \
        --name ${APP_NAME}-plan \
        --resource-group ${RESOURCE_GROUP} \
        --sku B2 \
        --is-linux

    # Create Web App
    print_info "Creating Web App..."
    az webapp create \
        --resource-group ${RESOURCE_GROUP} \
        --plan ${APP_NAME}-plan \
        --name ${APP_NAME} \
        --deployment-container-image-name ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

    # Configure app settings from .env
    print_info "Configuring app settings..."
    while IFS='=' read -r key value; do
        if [[ ! -z "$key" && ! "$key" =~ ^# ]]; then
            az webapp config appsettings set \
                --resource-group ${RESOURCE_GROUP} \
                --name ${APP_NAME} \
                --settings "${key}=${value}"
        fi
    done < .env

    # Enable logging
    az webapp log config \
        --resource-group ${RESOURCE_GROUP} \
        --name ${APP_NAME} \
        --application-logging filesystem \
        --level information

    print_success "Azure deployment completed"
    print_info "Web App URL: https://${APP_NAME}.azurewebsites.net"
}

# Run post-deployment tasks
post_deployment() {
    print_info "Running post-deployment tasks..."

    # Run database migrations if needed
    if [ "$DEPLOYMENT_TYPE" != "azure" ]; then
        print_info "Running database migrations..."
        # Add migration commands here if using Alembic
    fi

    # Verify deployment
    print_info "Verifying deployment..."

    case $DEPLOYMENT_TYPE in
        docker)
            HEALTH_URL="http://localhost:8000/api/health"
            ;;
        kubernetes)
            # Use port-forward for testing
            kubectl port-forward service/pr-validation-api 8080:8000 -n ${NAMESPACE} &
            PF_PID=$!
            sleep 5
            HEALTH_URL="http://localhost:8080/api/health"
            ;;
        azure)
            HEALTH_URL="https://${APP_NAME}.azurewebsites.net/api/health"
            ;;
    esac

    # Check health endpoint
    if curl -f ${HEALTH_URL} > /dev/null 2>&1; then
        print_success "Deployment verified - API is healthy"
    else
        print_warning "Could not verify deployment - please check manually"
    fi

    # Kill port-forward if used
    if [ ! -z "${PF_PID:-}" ]; then
        kill ${PF_PID} 2>/dev/null || true
    fi
}

# Main deployment flow
main() {
    print_info "Starting ${DEPLOYMENT_TYPE} deployment for ${ENVIRONMENT} environment..."

    # Check prerequisites
    check_prerequisites

    # Build Docker image (needed for all deployment types)
    build_docker_image

    # Push image if registry is configured
    if [ "$DEPLOYMENT_TYPE" != "docker" ]; then
        push_docker_image
    fi

    # Deploy based on type
    case $DEPLOYMENT_TYPE in
        docker)
            deploy_docker
            ;;
        kubernetes)
            deploy_kubernetes
            ;;
        azure)
            deploy_azure
            ;;
    esac

    # Run post-deployment tasks
    post_deployment

    print_success "Deployment completed successfully!"
    print_info ""
    print_info "Next steps:"
    print_info "1. Monitor the application logs"
    print_info "2. Set up monitoring and alerts"
    print_info "3. Configure backup strategies"
    print_info "4. Update Azure DevOps pipeline with the API endpoint"
}

# Run main function
main