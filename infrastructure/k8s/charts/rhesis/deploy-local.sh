#!/bin/bash

# Simple Helm deployment script for Rhesis
# This script handles namespace creation and prerequisites

set -e

RELEASE_NAME="rhesis"
CHART_PATH="."
VALUES_FILE="values-local.yaml"
NAMESPACE="rhesis"

echo "🚀 Deploying Rhesis using Helm (Simple Mode)"

# Function to check if Helm is available
check_helm() {
    if ! command -v helm &> /dev/null; then
        echo "❌ Helm is not installed or not in PATH"
        echo "Please install Helm: https://helm.sh/docs/intro/install/"
        exit 1
    fi
    echo "✅ Helm found: $(helm version --short)"
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo "❌ kubectl is not installed or not in PATH"
        exit 1
    fi
    echo "✅ kubectl found"
}

# Function to check and load Docker images into Minikube
load_images() {
    echo "🐳 Checking and loading Docker images..."
    
    # Check if we're running in Minikube
    if ! kubectl config current-context | grep -q minikube; then
        echo "⚠️  Not running in Minikube context, skipping image loading"
        return 0
    fi
    
    # List of required images
    local images=("rhesis-frontend:latest" "rhesis-backend:latest" "rhesis-worker:latest" "mirror.gcr.io/library/postgres:16-alpine" "mirror.gcr.io/library/redis:7-alpine")
    
    for image in "${images[@]}"; do
        echo "  - Checking image: $image"
        
        # Check if image exists locally
        if ! docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "^$image$"; then
            echo "    📥 Image $image not found locally, pulling..."
            if docker pull "$image"; then
                echo "    ✅ Image $image pulled successfully"
            else
                echo "    ❌ Failed to pull image $image"
                continue
            fi
        fi
        
        # Check if image is already loaded in Minikube
        if minikube image ls | grep -q "$image"; then
            echo "    ✅ Image $image already loaded in Minikube"
        else
            echo "    📦 Loading image $image into Minikube..."
            minikube image load "$image"
            echo "    ✅ Image $image loaded successfully"
        fi
    done
    
    echo "✅ Image loading completed"
}

# Function to create namespace if it doesn't exist
create_namespace() {
    echo "📦 Checking namespace: $NAMESPACE"
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        echo "📦 Creating namespace: $NAMESPACE"
        kubectl create namespace $NAMESPACE
        echo "✅ Namespace created"
    else
        echo "✅ Namespace already exists"
    fi
}

# Function to deploy with Helm (without wait flag to avoid timeouts)
deploy_with_helm() {
    echo "🚀 Deploying with Helm..."
    
    # Check if release already exists
    if helm list -n $NAMESPACE 2>/dev/null | grep -q $RELEASE_NAME; then
        echo "🔄 Upgrading existing release: $RELEASE_NAME"
        helm upgrade $RELEASE_NAME $CHART_PATH \
            --values $VALUES_FILE \
            --namespace $NAMESPACE \
            --timeout 5m
    else
        echo "🆕 Installing new release: $RELEASE_NAME"
        helm install $RELEASE_NAME $CHART_PATH \
            --values $VALUES_FILE \
            --namespace $NAMESPACE \
            --timeout 5m
    fi
    
    echo "✅ Helm deployment completed"
}

# Function to apply secrets and configmaps after namespace creation
apply_prerequisites() {
    echo "📋 Applying secrets and configmaps..."
    
    # Apply secrets and configmaps directly (namespace is already active)
    kubectl apply -f ../../manifests/secrets/ -n $NAMESPACE
    kubectl apply -f ../../manifests/configmaps/ -n $NAMESPACE
    
    echo "✅ Prerequisites applied"
}

# Function to wait for resources to be ready
wait_for_resources() {
    echo "⏳ Waiting for resources to be ready..."
    
    # Wait for deployments to be available
    echo "  - Waiting for PostgreSQL deployment..."
    kubectl wait --for=condition=available --timeout=300s deployment/postgres -n $NAMESPACE
    
    echo "  - Waiting for Redis deployment..."
    kubectl wait --for=condition=available --timeout=300s deployment/redis -n $NAMESPACE
    
    echo "  - Waiting for Backend deployment..."
    kubectl wait --for=condition=available --timeout=300s deployment/backend -n $NAMESPACE
    
    echo "  - Waiting for Frontend deployment..."
    kubectl wait --for=condition=available --timeout=300s deployment/frontend -n $NAMESPACE
    
    echo "  - Waiting for Worker deployment..."
    kubectl wait --for=condition=available --timeout=300s deployment/worker -n $NAMESPACE
    
    echo "✅ All deployments are ready"
}

# Function to show deployment status
show_status() {
    echo ""
    echo "📊 Deployment Status:"
    helm status $RELEASE_NAME -n $NAMESPACE
    
    echo ""
    echo "🔍 Pod Status:"
    kubectl get pods -n $NAMESPACE
    
    echo ""
    echo "🌐 Services:"
    kubectl get services -n $NAMESPACE
}

# Function to show access instructions
show_access_instructions() {
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "🌐 To access your application:"
    echo ""
    echo "Frontend (Next.js):"
    echo "  kubectl port-forward -n $NAMESPACE svc/frontend 3000:3000"
    echo "  Then open: http://localhost:3000"
    echo ""
    echo "Backend (FastAPI):"
    echo "  kubectl port-forward -n $NAMESPACE svc/backend 8080:8080"
    echo "  Then open: http://localhost:8080"
    echo ""
    echo "Worker Health Check:"
    echo "  kubectl port-forward -n $NAMESPACE svc/worker 8080:8080"
    echo "  Then check: http://localhost:8080/health/basic"
    echo ""
    echo "📚 For more information, run: helm status $RELEASE_NAME -n $NAMESPACE"
}

# Main deployment flow
main() {
    check_helm
    check_kubectl
    load_images
    create_namespace
    deploy_with_helm
    apply_prerequisites
    wait_for_resources
    show_status
    show_access_instructions
}

# Run main function
main
