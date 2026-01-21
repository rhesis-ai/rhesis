#!/bin/bash

# Rebuild and Redeploy Script for Rhesis Kubernetes Deployment
# This script:
# 1. Deletes old images from Minikube
# 2. Deletes volumes (PVCs and PVs)
# 3. Rebuilds Docker images
# 4. Loads images into Minikube
# 5. Redeploys the application

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NAMESPACE="rhesis"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Rhesis Kubernetes - Rebuild and Redeploy${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker found${NC}"
    
    if ! command -v minikube &> /dev/null; then
        echo -e "${RED}❌ Minikube is not installed or not in PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Minikube found${NC}"
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ kubectl found${NC}"
    
    if ! command -v helm &> /dev/null; then
        echo -e "${RED}❌ Helm is not installed or not in PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Helm found${NC}"
    
    # Check if Minikube is running
    if ! minikube status &> /dev/null; then
        echo -e "${YELLOW}⚠️  Minikube is not running. Starting Minikube...${NC}"
        minikube start --driver=docker --memory=8192 --cpus=2 --addons=storage-provisioner --addons=default-storageclass
    else
        echo -e "${GREEN}✅ Minikube is running${NC}"
    fi
    
    # Check if we're using Minikube context
    if ! kubectl config current-context | grep -q minikube; then
        echo -e "${YELLOW}⚠️  Not using Minikube context. Switching to Minikube...${NC}"
        kubectl config use-context minikube
    fi
    
    echo ""
}

# Function to delete old images from Minikube
delete_old_images() {
    echo -e "${YELLOW}🗑️  Step 1: Deleting old images from Minikube...${NC}"
    
    local images=("rhesis-frontend:latest" "rhesis-backend:latest" "rhesis-worker:latest")
    
    for image in "${images[@]}"; do
        echo -e "  - Removing image: ${BLUE}$image${NC}"
        if minikube image rm "$image" 2>/dev/null; then
            echo -e "    ${GREEN}✅ Removed $image${NC}"
        else
            echo -e "    ${YELLOW}⚠️  Image $image not found in Minikube (may not exist)${NC}"
        fi
    done
    
    echo -e "${GREEN}✅ Image cleanup completed${NC}"
    echo ""
}

# Function to delete volumes and cleanup resources
delete_volumes() {
    echo -e "${YELLOW}🗑️  Step 2: Deleting volumes and cleaning up resources...${NC}"
    
    # Scale down all deployments first
    echo -e "  - Scaling down deployments...${NC}"
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        kubectl scale deployment --all --replicas=0 -n "$NAMESPACE" 2>/dev/null || true
        echo -e "    ${GREEN}✅ Deployments scaled down${NC}"
    else
        echo -e "    ${YELLOW}⚠️  Namespace $NAMESPACE does not exist${NC}"
    fi
    
    # Delete all pods in namespace
    echo -e "  - Deleting pods...${NC}"
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        kubectl delete pods --all -n "$NAMESPACE" 2>/dev/null || true
        echo -e "    ${GREEN}✅ Pods deleted${NC}"
    fi
    
    # Delete all PVCs (Persistent Volume Claims)
    echo -e "  - Deleting Persistent Volume Claims...${NC}"
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        kubectl delete pvc --all -n "$NAMESPACE" 2>/dev/null || true
        echo -e "    ${GREEN}✅ PVCs deleted${NC}"
    fi
    
    # Delete all PVs (Persistent Volumes) - these are cluster-scoped
    echo -e "  - Deleting Persistent Volumes...${NC}"
    kubectl delete pv --all 2>/dev/null || true
    echo -e "    ${GREEN}✅ PVs deleted${NC}"
    
    # Uninstall Helm release if it exists
    echo -e "  - Uninstalling Helm release...${NC}"
    if helm list -n "$NAMESPACE" 2>/dev/null | grep -q rhesis; then
        helm uninstall rhesis -n "$NAMESPACE" 2>/dev/null || true
        echo -e "    ${GREEN}✅ Helm release uninstalled${NC}"
    else
        echo -e "    ${YELLOW}⚠️  No Helm release found${NC}"
    fi
    
    echo -e "${GREEN}✅ Volume cleanup completed${NC}"
    echo ""
}

# Function to rebuild Docker images
rebuild_images() {
    echo -e "${YELLOW}🔨 Step 3: Rebuilding Docker images...${NC}"
    
    cd "$PROJECT_ROOT" || {
        echo -e "${RED}❌ Error: Project root directory not found${NC}"
        exit 1
    }
    
    # Build frontend (can be built from its own directory)
    echo -e "  - Building frontend image...${NC}"
    cd apps/frontend || {
        echo -e "${RED}❌ Error: Frontend directory not found${NC}"
        exit 1
    }
    docker build -t rhesis-frontend:latest . --build-arg FRONTEND_ENV=local --build-arg NEXT_PUBLIC_QUICK_START=true
    echo -e "    ${GREEN}✅ Frontend image built${NC}"
    
    # Build backend (must be built from project root with -f flag)
    echo -e "  - Building backend image...${NC}"
    cd "$PROJECT_ROOT" || {
        echo -e "${RED}❌ Error: Project root directory not found${NC}"
        exit 1
    }
    docker build -t rhesis-backend:latest . -f apps/backend/Dockerfile --build-arg QUICK_START=true 
    echo -e "    ${GREEN}✅ Backend image built${NC}"
    
    # Build worker (must be built from project root with -f flag)
    echo -e "  - Building worker image...${NC}"
    cd "$PROJECT_ROOT" || {
        echo -e "${RED}❌ Error: Project root directory not found${NC}"
        exit 1
    }
    docker build -t rhesis-worker:latest -f apps/worker/Dockerfile .
    echo -e "    ${GREEN}✅ Worker image built${NC}"
    
    echo -e "${GREEN}✅ All images rebuilt successfully${NC}"
    echo ""
}

# Function to load images into Minikube
load_images() {
    echo -e "${YELLOW}📦 Step 4: Loading images into Minikube...${NC}"
    
    local images=("rhesis-frontend:latest" "rhesis-backend:latest" "rhesis-worker:latest")
    
    for image in "${images[@]}"; do
        echo -e "  - Loading image: ${BLUE}$image${NC}"
        if minikube image load "$image"; then
            echo -e "    ${GREEN}✅ Loaded $image${NC}"
        else
            echo -e "    ${RED}❌ Failed to load $image${NC}"
            exit 1
        fi
    done
    
    echo -e "${GREEN}✅ All images loaded into Minikube${NC}"
    echo ""
}

# Function to deploy
deploy() {
    echo -e "${YELLOW}🚀 Step 5: Deploying application...${NC}"
    
    cd "$PROJECT_ROOT/infrastructure/k8s/charts/rhesis" || {
        echo -e "${RED}❌ Error: Helm chart directory not found${NC}"
        exit 1
    }
    
    # Make deploy script executable
    chmod +x deploy-local.sh
    
    # Run deployment script
    ./deploy-local.sh
    
    echo -e "${GREEN}✅ Deployment completed${NC}"
    echo ""
}

# Main execution
main() {
    check_prerequisites
    delete_old_images
    delete_volumes
    rebuild_images
    load_images
    deploy
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 Rebuild and deployment completed successfully!${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo -e "  ${BLUE}1.${NC} Check pod status: ${GREEN}kubectl get pods -n $NAMESPACE${NC}"
    echo -e "  ${BLUE}2.${NC} Port-forward frontend: ${GREEN}kubectl port-forward -n $NAMESPACE svc/frontend 3000:3000${NC}"
    echo -e "  ${BLUE}3.${NC} Port-forward backend: ${GREEN}kubectl port-forward -n $NAMESPACE svc/backend 8080:8080${NC}"
    echo ""
}

# Run main function
main

