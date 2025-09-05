#!/bin/bash

# Rhesis Kubernetes Deployment Script
# Usage: ./deploy.sh [dev|staging|prod]

set -e

ENVIRONMENT=${1:-dev}
NAMESPACE="rhesis"

echo "🚀 Deploying Rhesis to Kubernetes (${ENVIRONMENT} environment)"

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo "❌ kubectl is not installed or not in PATH"
        exit 1
    fi
}

# Function to check if namespace exists
check_namespace() {
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        echo "📦 Creating namespace: $NAMESPACE"
        kubectl apply -f manifests/namespaces/
    fi
}

# Function to deploy base resources
deploy_base() {
    echo "📋 Deploying base resources..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MANIFESTS_DIR="$SCRIPT_DIR/../manifests"
    
    # Apply ConfigMaps
    echo "  - ConfigMaps"
    kubectl apply -f "$MANIFESTS_DIR/configmaps/"
    
    # Apply Secrets
    echo "  - Secrets"
    kubectl apply -f "$MANIFESTS_DIR/secrets/"
    
    # Apply storage
    echo "  - Storage (PVs/PVCs)"
    kubectl apply -f "$MANIFESTS_DIR/storage/postgres/"
    kubectl apply -f "$MANIFESTS_DIR/storage/redis/"
    
    # Apply services
    echo "  - Services"
    kubectl apply -f "$MANIFESTS_DIR/services/postgres/"
    kubectl apply -f "$MANIFESTS_DIR/services/redis/"
    kubectl apply -f "$MANIFESTS_DIR/services/backend/"
    kubectl apply -f "$MANIFESTS_DIR/services/frontend/"
    kubectl apply -f "$MANIFESTS_DIR/services/worker/"
}

# Function to deploy applications
deploy_applications() {
    echo "🚀 Deploying applications..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MANIFESTS_DIR="$SCRIPT_DIR/../manifests"
    
    # Deploy PostgreSQL
    echo "  - PostgreSQL"
    kubectl apply -f "$MANIFESTS_DIR/deployments/postgres/"
    
    # Wait for PostgreSQL to be ready
    echo "⏳ Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s
    
    # Deploy other components
    echo "  - Redis"
    kubectl apply -f "$MANIFESTS_DIR/deployments/redis/"
    
    echo "  - Backend"
    kubectl apply -f "$MANIFESTS_DIR/deployments/backend/"
    
    echo "  - Frontend"
    kubectl apply -f "$MANIFESTS_DIR/deployments/frontend/"
    
    echo "  - Worker"
    kubectl apply -f "$MANIFESTS_DIR/deployments/worker/"
}

# Function to show deployment status
show_status() {
    echo "📊 Deployment Status:"
    kubectl get all -n $NAMESPACE
    
    echo ""
    echo "🔍 Pod Status:"
    kubectl get pods -n $NAMESPACE
    
    echo ""
    echo "💾 Storage Status:"
    kubectl get pv,pvc -n $NAMESPACE
}

# Main deployment flow
main() {
    check_kubectl
    check_namespace
    deploy_base
    deploy_applications
    show_status
    
    echo ""
    echo "✅ Deployment completed successfully!"
    echo "🌐 Access your application:"
    echo "   - Frontend: kubectl port-forward -n $NAMESPACE svc/frontend 3000:3000"
    echo "   - Backend: kubectl port-forward -n $NAMESPACE svc/backend 8080:8080"
}

# Run main function
main
