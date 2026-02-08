#!/bin/bash

# Rhesis Kubernetes Management Script
# A friendly tool to manage your Rhesis Kubernetes deployment

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NAMESPACE="rhesis"

# Service names
SERVICES=("frontend" "backend" "worker" "chatbot" "docs")

# Print banner
print_banner() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🚀 Rhesis Kubernetes Management Tool${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Print usage
print_usage() {
    cat << EOF
${YELLOW}Usage:${NC}
  $0 <command> [options]

${YELLOW}Commands:${NC}
  ${GREEN}clean${NC}                      Full clean install (delete everything, rebuild, deploy)
  ${GREEN}update${NC}                     Hot update configs (no rebuild, just apply values changes)
  ${GREEN}rebuild${NC} [service]          Rebuild images (all or specific: frontend, backend, worker, chatbot, docs)
  ${GREEN}restart${NC} <service>          Restart a specific service
  ${GREEN}logs${NC} <service> [--follow]  View logs of a service (use -f or --follow for live logs)
  ${GREEN}shell${NC} <service>            Open a shell in a service pod
  ${GREEN}db${NC}                         Connect to PostgreSQL database
  ${GREEN}redis${NC}                      Connect to Redis
  ${GREEN}status${NC}                     Show status of all pods and services
  ${GREEN}port-forward${NC} [service]     Quick port forwarding (all or specific service)
  ${GREEN}kill${NC} [service]             Kill port-forward processes (all or specific service)
  ${GREEN}scale${NC} <service> <replicas> Scale a service to N replicas
  ${GREEN}help${NC}                       Show this help message

${YELLOW}Examples:${NC}
  $0 clean                    # Fresh start - deletes everything and redeploys
  $0 update                   # Apply values-local.yaml changes without rebuild
  $0 rebuild backend          # Rebuild only backend image
  $0 rebuild                  # Rebuild all images
  $0 logs backend --follow    # Watch backend logs in real-time
  $0 shell backend            # Open bash shell in backend pod
  $0 db                       # Connect to PostgreSQL
  $0 restart frontend         # Restart frontend pods
  $0 status                   # See what's running
  $0 kill                     # Kill all port-forward processes
  $0 kill backend             # Kill only backend port-forward

${CYAN}💡 Pro Tips:${NC}
  • Use 'update' when you only change configs or resource limits
  • Use 'rebuild' when you change application code
  • Use 'clean' when things go sideways and you want a fresh start
  • Press Ctrl+C to exit logs or shells

EOF
}

# Check prerequisites
check_prerequisites() {
    local commands=("docker" "minikube" "kubectl" "helm")
    local missing=()
    
    for cmd in "${commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}❌ Missing required tools: ${missing[*]}${NC}"
        echo -e "${YELLOW}Please install them and try again.${NC}"
        exit 1
    fi
    
    # Check if Minikube is running
    if ! minikube status &> /dev/null; then
        echo -e "${YELLOW}⚠️  Minikube is not running. Starting Minikube...${NC}"
        minikube start --driver=docker --memory=8192 --cpus=2 \
            --addons=storage-provisioner --addons=default-storageclass
    fi
    
    # Check if we're using Minikube context
    if ! kubectl config current-context | grep -q minikube; then
        echo -e "${YELLOW}⚠️  Switching to Minikube context...${NC}"
        kubectl config use-context minikube
    fi
}

# Delete old images from Minikube
delete_old_images() {
    local service=$1
    echo -e "${YELLOW}🗑️  Deleting old images...${NC}"
    
    if [ -n "$service" ]; then
        local image="rhesis-$service:latest"
        echo -e "  - Removing image: ${BLUE}$image${NC}"
        minikube image rm "$image" 2>/dev/null || echo -e "    ${YELLOW}⚠️  Image not found${NC}"
    else
        for svc in "${SERVICES[@]}"; do
            local image="rhesis-$svc:latest"
            echo -e "  - Removing image: ${BLUE}$image${NC}"
            minikube image rm "$image" 2>/dev/null || echo -e "    ${YELLOW}⚠️  Image not found${NC}"
        done
    fi
    
    echo -e "${GREEN}✅ Image cleanup completed${NC}"
    echo ""
}

# Delete volumes and cleanup resources
delete_volumes() {
    echo -e "${YELLOW}🗑️  Deleting volumes and cleaning up resources...${NC}"
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo -e "    ${YELLOW}⚠️  Namespace $NAMESPACE does not exist${NC}"
        return
    fi
    
    echo -e "  - Scaling down deployments...${NC}"
    kubectl scale deployment --all --replicas=0 -n "$NAMESPACE" 2>/dev/null || true
    echo -e "    ${GREEN}✅ Deployments scaled down${NC}"
    
    echo -e "  - Deleting pods...${NC}"
    kubectl delete pods --all -n "$NAMESPACE" 2>/dev/null || true
    echo -e "    ${GREEN}✅ Pods deleted${NC}"
    
    echo -e "  - Collecting PVs bound to rhesis namespace...${NC}"
    # Get PVs that are bound to PVCs in the rhesis namespace
    local rhesis_pvs=$(kubectl get pvc -n "$NAMESPACE" -o jsonpath='{.items[*].spec.volumeName}' 2>/dev/null || echo "")
    
    echo -e "  - Deleting Persistent Volume Claims...${NC}"
    kubectl delete pvc --all -n "$NAMESPACE" 2>/dev/null || true
    echo -e "    ${GREEN}✅ PVCs deleted${NC}"
    
    # Only delete PVs that were specifically bound to rhesis namespace
    if [ -n "$rhesis_pvs" ]; then
        echo -e "  - Deleting Persistent Volumes (only rhesis namespace PVs)...${NC}"
        for pv in $rhesis_pvs; do
            if [ -n "$pv" ]; then
                echo -e "    ${BLUE}Deleting PV: $pv${NC}"
                kubectl delete pv "$pv" 2>/dev/null || true
            fi
        done
        echo -e "    ${GREEN}✅ Rhesis PVs deleted${NC}"
    else
        echo -e "    ${YELLOW}⚠️  No PVs found for rhesis namespace${NC}"
    fi
    
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

# Build a specific service image
build_service_image() {
    local service=$1
    echo -e "  - Building ${BLUE}$service${NC} image...${NC}"
    
    case $service in
        frontend)
            cd "$PROJECT_ROOT/apps/frontend" || exit 1
            docker build -t rhesis-frontend:latest . \
                --build-arg FRONTEND_ENV=local \
                --build-arg NEXT_PUBLIC_QUICK_START=false \
                --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8080 \
                --build-arg NEXT_PUBLIC_APP_URL=http://localhost:3000
            ;;
        backend)
            cd "$PROJECT_ROOT" || exit 1
            docker build -t rhesis-backend:latest . -f apps/backend/Dockerfile \
                --build-arg QUICK_START=false
            ;;
        worker)
            cd "$PROJECT_ROOT" || exit 1
            docker build -t rhesis-worker:latest -f apps/worker/Dockerfile .
            ;;
        chatbot)
            cd "$PROJECT_ROOT" || exit 1
            docker build -t rhesis-chatbot:latest -f apps/chatbot/Dockerfile .
            ;;
        docs)
            cd "$PROJECT_ROOT/docs" || exit 1
            docker build -t rhesis-docs:latest -f src/Dockerfile .
            ;;
        *)
            echo -e "${RED}❌ Unknown service: $service${NC}"
            return 1
            ;;
    esac
    
    echo -e "    ${GREEN}✅ $service image built${NC}"
}

# Rebuild Docker images
rebuild_images() {
    local service=$1
    echo -e "${YELLOW}🔨 Rebuilding Docker images...${NC}"
    
    if [ -n "$service" ]; then
        build_service_image "$service"
    else
        for svc in "${SERVICES[@]}"; do
            build_service_image "$svc"
        done
    fi
    
    echo -e "${GREEN}✅ Image build completed${NC}"
    echo ""
}

# Load images into Minikube
load_images() {
    local service=$1
    echo -e "${YELLOW}📦 Loading images into Minikube...${NC}"
    
    if [ -n "$service" ]; then
        local image="rhesis-$service:latest"
        echo -e "  - Loading image: ${BLUE}$image${NC}"
        minikube image load "$image"
        echo -e "    ${GREEN}✅ Loaded $image${NC}"
    else
        for svc in "${SERVICES[@]}"; do
            local image="rhesis-$svc:latest"
            echo -e "  - Loading image: ${BLUE}$image${NC}"
            minikube image load "$image"
            echo -e "    ${GREEN}✅ Loaded $image${NC}"
        done
    fi
    
    echo -e "${GREEN}✅ All images loaded into Minikube${NC}"
    echo ""
}

# Deploy or update application
deploy() {
    echo -e "${YELLOW}🚀 Deploying application...${NC}"
    
    cd "$PROJECT_ROOT/infrastructure/k8s/charts/rhesis" || exit 1
    
    chmod +x deploy-local.sh
    ./deploy-local.sh
    
    echo -e "${GREEN}✅ Deployment completed${NC}"
    echo ""
}

# Update configuration without rebuilding images
update_config() {
    echo -e "${YELLOW}🔄 Updating configuration...${NC}"
    
    cd "$PROJECT_ROOT/infrastructure/k8s/charts/rhesis" || exit 1
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo -e "${RED}❌ Namespace $NAMESPACE does not exist. Run 'clean' first.${NC}"
        exit 1
    fi
    
    if ! helm list -n "$NAMESPACE" 2>/dev/null | grep -q rhesis; then
        echo -e "${RED}❌ Helm release not found. Run 'clean' first.${NC}"
        exit 1
    fi
    
    echo -e "  - Upgrading Helm release with new values...${NC}"
    helm upgrade rhesis . \
        --values values-local.yaml \
        --namespace "$NAMESPACE" \
        --wait \
        --timeout 10m
    
    echo -e "${GREEN}✅ Configuration updated${NC}"
    echo ""
}

# Get pod name for a service
get_pod_name() {
    local service=$1
    kubectl get pods -n "$NAMESPACE" -l "app=$service" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

# Show logs
show_logs() {
    local service=$1
    local follow=$2
    
    if [ -z "$service" ]; then
        echo -e "${RED}❌ Please specify a service: ${SERVICES[*]}${NC}"
        exit 1
    fi
    
    local pod=$(get_pod_name "$service")
    if [ -z "$pod" ]; then
        echo -e "${RED}❌ No pod found for service: $service${NC}"
        exit 1
    fi
    
    echo -e "${CYAN}📋 Showing logs for ${BLUE}$service${CYAN} (pod: $pod)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
    echo ""
    
    if [ "$follow" = "true" ]; then
        kubectl logs -n "$NAMESPACE" -f "$pod"
    else
        kubectl logs -n "$NAMESPACE" "$pod" --tail=100
    fi
}

# Open shell in pod
open_shell() {
    local service=$1
    
    if [ -z "$service" ]; then
        echo -e "${RED}❌ Please specify a service: ${SERVICES[*]}${NC}"
        exit 1
    fi
    
    local pod=$(get_pod_name "$service")
    if [ -z "$pod" ]; then
        echo -e "${RED}❌ No pod found for service: $service${NC}"
        exit 1
    fi
    
    echo -e "${CYAN}🐚 Opening shell in ${BLUE}$service${CYAN} (pod: $pod)${NC}"
    echo -e "${YELLOW}Type 'exit' to close the shell${NC}"
    echo ""
    
    kubectl exec -it -n "$NAMESPACE" "$pod" -- /bin/sh || \
    kubectl exec -it -n "$NAMESPACE" "$pod" -- /bin/bash
}

# Connect to database
connect_db() {
    echo -e "${CYAN}🗄️  Connecting to PostgreSQL database...${NC}"
    
    local pod=$(get_pod_name "postgres")
    if [ -z "$pod" ]; then
        echo -e "${RED}❌ PostgreSQL pod not found${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Database: rhesis-db | User: rhesis-user${NC}"
    echo -e "${YELLOW}Type \\q to exit${NC}"
    echo ""
    
    kubectl exec -it -n "$NAMESPACE" "$pod" -- \
        psql -U rhesis-user -d rhesis-db
}

# Connect to Redis
connect_redis() {
    echo -e "${CYAN}🔴 Connecting to Redis...${NC}"
    
    local pod=$(get_pod_name "redis")
    if [ -z "$pod" ]; then
        echo -e "${RED}❌ Redis pod not found${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Type 'exit' to close${NC}"
    echo ""
    
    kubectl exec -it -n "$NAMESPACE" "$pod" -- redis-cli
}

# Show status
show_status() {
    echo -e "${CYAN}📊 Rhesis Cluster Status${NC}"
    echo ""
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo -e "${YELLOW}⚠️  Namespace $NAMESPACE does not exist${NC}"
        echo -e "${YELLOW}Run: $0 clean${NC}"
        return
    fi
    
    echo -e "${BLUE}Pods:${NC}"
    kubectl get pods -n "$NAMESPACE" -o wide
    echo ""
    
    echo -e "${BLUE}Services:${NC}"
    kubectl get svc -n "$NAMESPACE"
    echo ""
    
    echo -e "${BLUE}Persistent Volume Claims:${NC}"
    kubectl get pvc -n "$NAMESPACE"
    echo ""
    
    echo -e "${BLUE}Helm Releases:${NC}"
    helm list -n "$NAMESPACE"
    echo ""
}

# Port forward
port_forward() {
    local service=$1
    
    if [ -z "$service" ]; then
        echo -e "${CYAN}🌐 Starting port forwarding for all services...${NC}"
        echo -e "${YELLOW}Run these commands in separate terminals:${NC}"
        echo ""
        echo -e "${GREEN}kubectl port-forward -n $NAMESPACE svc/frontend 3000:3000${NC}"
        echo -e "${GREEN}kubectl port-forward -n $NAMESPACE svc/backend 8080:8080${NC}"
        echo -e "${GREEN}kubectl port-forward -n $NAMESPACE svc/chatbot 8083:8083${NC}"
        echo -e "${GREEN}kubectl port-forward -n $NAMESPACE svc/docs 3001:3001${NC}"
        echo ""
        echo -e "${YELLOW}Or run them in background:${NC}"
        echo -e "${GREEN}$0 port-forward all &${NC}"
        return
    fi
    
    case $service in
        frontend)
            echo -e "${CYAN}🌐 Port forwarding frontend: http://localhost:3000${NC}"
            kubectl port-forward -n "$NAMESPACE" svc/frontend 3000:3000
            ;;
        backend)
            echo -e "${CYAN}🌐 Port forwarding backend: http://localhost:8080${NC}"
            kubectl port-forward -n "$NAMESPACE" svc/backend 8080:8080
            ;;
        chatbot)
            echo -e "${CYAN}🌐 Port forwarding chatbot: http://localhost:8083${NC}"
            kubectl port-forward -n "$NAMESPACE" svc/chatbot 8083:8083
            ;;
        docs)
            echo -e "${CYAN}🌐 Port forwarding docs: http://localhost:3001${NC}"
            kubectl port-forward -n "$NAMESPACE" svc/docs 3001:3001
            ;;
        all)
            echo -e "${CYAN}🌐 Starting all port forwards in background...${NC}"
            kubectl port-forward -n "$NAMESPACE" svc/frontend 3000:3000 &
            kubectl port-forward -n "$NAMESPACE" svc/backend 8080:8080 &
            kubectl port-forward -n "$NAMESPACE" svc/chatbot 8083:8083 &
            kubectl port-forward -n "$NAMESPACE" svc/docs 3001:3001 &
            echo -e "${GREEN}✅ All port forwards started${NC}"
            echo -e "${YELLOW}Run 'killall kubectl' to stop all port forwards${NC}"
            ;;
        *)
            echo -e "${RED}❌ Unknown service: $service${NC}"
            echo -e "${YELLOW}Available: frontend, backend, chatbot, docs, all${NC}"
            exit 1
            ;;
    esac
}

# Kill port forward processes
kill_port_forwards() {
    local service=$1
    
    echo -e "${YELLOW}🔪 Killing port-forward processes...${NC}"
    
    # Get all kubectl port-forward processes
    local pids=$(ps aux | grep 'kubectl port-forward' | grep -v grep | awk '{print $2}')
    
    if [ -z "$pids" ]; then
        echo -e "${YELLOW}⚠️  No port-forward processes found${NC}"
        return
    fi
    
    if [ -z "$service" ]; then
        # Kill all port-forward processes
        echo -e "  - Killing all port-forward processes...${NC}"
        while read -r pid; do
            if [ -n "$pid" ]; then
                local cmd=$(ps -p "$pid" -o command= 2>/dev/null || echo "unknown")
                echo -e "    ${BLUE}Killing PID $pid: $cmd${NC}"
                kill "$pid" 2>/dev/null || true
            fi
        done <<< "$pids"
        echo -e "${GREEN}✅ All port-forward processes killed${NC}"
    else
        # Kill specific service port-forward
        local port=""
        case $service in
            frontend)
                port="3000"
                ;;
            backend)
                port="8080"
                ;;
            chatbot)
                port="8083"
                ;;
            docs)
                port="3001"
                ;;
            *)
                echo -e "${RED}❌ Unknown service: $service${NC}"
                echo -e "${YELLOW}Available: frontend, backend, chatbot, docs${NC}"
                exit 1
                ;;
        esac
        
        echo -e "  - Killing port-forward for ${BLUE}$service${NC} (port $port)...${NC}"
        local killed=0
        while read -r pid; do
            if [ -n "$pid" ]; then
                local cmd=$(ps -p "$pid" -o command= 2>/dev/null || echo "")
                if echo "$cmd" | grep -q "svc/$service" || echo "$cmd" | grep -q ":$port"; then
                    echo -e "    ${BLUE}Killing PID $pid: $cmd${NC}"
                    kill "$pid" 2>/dev/null || true
                    killed=1
                fi
            fi
        done <<< "$pids"
        
        if [ "$killed" -eq 0 ]; then
            echo -e "${YELLOW}⚠️  No port-forward process found for $service${NC}"
        else
            echo -e "${GREEN}✅ Port-forward for $service killed${NC}"
        fi
    fi
    
    echo ""
}

# Scale deployment
scale_deployment() {
    local service=$1
    local replicas=$2
    
    if [ -z "$service" ] || [ -z "$replicas" ]; then
        echo -e "${RED}❌ Usage: $0 scale <service> <replicas>${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}📏 Scaling $service to $replicas replicas...${NC}"
    kubectl scale deployment "$service" --replicas="$replicas" -n "$NAMESPACE"
    echo -e "${GREEN}✅ Scaled $service to $replicas replicas${NC}"
}

# Restart service
restart_service() {
    local service=$1
    
    if [ -z "$service" ]; then
        echo -e "${RED}❌ Please specify a service: ${SERVICES[*]}${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}🔄 Restarting $service...${NC}"
    kubectl rollout restart deployment "$service" -n "$NAMESPACE"
    kubectl rollout status deployment "$service" -n "$NAMESPACE"
    echo -e "${GREEN}✅ $service restarted${NC}"
}

# Clean install
clean_install() {
    print_banner
    echo -e "${YELLOW}🧹 Starting clean installation...${NC}"
    echo -e "${RED}This will delete all data including databases!${NC}"
    echo ""
    
    check_prerequisites
    delete_old_images
    delete_volumes
    rebuild_images
    load_images
    deploy
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 Clean installation completed!${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    show_status
}

# Rebuild and redeploy (keep data)
rebuild_and_redeploy() {
    local service=$1
    print_banner
    echo -e "${YELLOW}🔨 Rebuilding and redeploying...${NC}"
    
    check_prerequisites
    delete_old_images "$service"
    rebuild_images "$service"
    load_images "$service"
    
    if [ -n "$service" ]; then
        restart_service "$service"
    else
        # Restart all services to pick up new images
        echo -e "${YELLOW}🔄 Restarting all services to pick up new images...${NC}"
        for svc in "${SERVICES[@]}"; do
            echo -e "  - Restarting ${BLUE}$svc${NC}...${NC}"
            if kubectl get deployment "$svc" -n "$NAMESPACE" &> /dev/null; then
                kubectl rollout restart deployment "$svc" -n "$NAMESPACE"
            else
                echo -e "    ${YELLOW}⚠️  Deployment $svc not found, skipping${NC}"
            fi
        done
        
        # Wait for all rollouts to complete
        echo -e "${YELLOW}⏳ Waiting for all rollouts to complete...${NC}"
        for svc in "${SERVICES[@]}"; do
            if kubectl get deployment "$svc" -n "$NAMESPACE" &> /dev/null; then
                echo -e "  - Waiting for ${BLUE}$svc${NC}...${NC}"
                kubectl rollout status deployment "$svc" -n "$NAMESPACE" --timeout=5m || true
            fi
        done
        echo -e "${GREEN}✅ All services restarted${NC}"
    fi
    
    echo -e "${GREEN}🎉 Rebuild and redeploy completed!${NC}"
    echo ""
}

# Main command handler
main() {
    local command=$1
    shift
    
    case $command in
        clean)
            clean_install
            ;;
        update)
            print_banner
            check_prerequisites
            update_config
            echo -e "${GREEN}🎉 Configuration updated!${NC}"
            ;;
        rebuild)
            rebuild_and_redeploy "$@"
            ;;
        logs)
            local service=$1
            local follow="false"
            if [ "$2" = "-f" ] || [ "$2" = "--follow" ]; then
                follow="true"
            fi
            show_logs "$service" "$follow"
            ;;
        shell)
            open_shell "$1"
            ;;
        db)
            connect_db
            ;;
        redis)
            connect_redis
            ;;
        status)
            show_status
            ;;
        port-forward)
            port_forward "$1"
            ;;
        kill)
            kill_port_forwards "$1"
            ;;
        scale)
            scale_deployment "$1" "$2"
            ;;
        restart)
            check_prerequisites
            restart_service "$1"
            ;;
        help|--help|-h)
            print_banner
            print_usage
            ;;
        *)
            print_banner
            echo -e "${RED}❌ Unknown command: $command${NC}"
            echo ""
            print_usage
            exit 1
            ;;
    esac
}

# Run main
if [ $# -eq 0 ]; then
    print_banner
    print_usage
    exit 1
fi

main "$@"
