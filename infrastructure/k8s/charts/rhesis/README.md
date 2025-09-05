# 🚀 Rhesis Helm Chart

A Helm chart for deploying the Rhesis AI application stack to Kubernetes.

## 📋 Overview

This Helm chart deploys the complete Rhesis application stack including:
- 🗄️ **PostgreSQL** - Database with persistent storage
- 🔴 **Redis** - Cache and message broker
- ⚙️ **Backend** - FastAPI application
- 🎨 **Frontend** - Next.js application
- 🔄 **Worker** - Celery worker for background tasks

## 🎯 Features

- **Environment-specific configurations** - Easy switching between dev/staging/prod
- **Conditional deployments** - Enable/disable components as needed
- **Persistent storage** - Configurable storage for databases
- **Health checks** - Built-in liveness and readiness probes
- **Resource management** - Configurable CPU and memory limits
- **Local development ready** - Optimized for Minikube and local clusters

## 📦 Prerequisites

- Kubernetes cluster (Minikube, Docker Desktop, or cloud)
- Helm 3.x installed
- kubectl configured
- Docker images built and available locally

## 💻 System Requirements

### Minimum Requirements
- **CPU**: 4 cores (2.0 GHz)
- **RAM**: 8 GB
- **Storage**: 20 GB free space
- **OS**: Linux, macOS, or Windows with Docker support

### Recommended Requirements
- **CPU**: 8 cores (2.5 GHz)
- **RAM**: 16 GB
- **Storage**: 50 GB free space (SSD recommended)
- **OS**: Linux or macOS

### Kubernetes Cluster Requirements
- **Minikube**: v1.28+ with 8GB+ memory allocation
- **Docker Desktop**: 4GB+ memory for Kubernetes
- **Cloud**: Any managed Kubernetes service (GKE, EKS, AKS)

## 📊 Resource Usage

### Local Development Configuration

| Component | Replicas | CPU Requests | CPU Limits | Memory Requests | Memory Limits | Storage |
|-----------|----------|--------------|------------|-----------------|---------------|---------|
| **Frontend** | 1 | 1000m | 2000m | 2 Gi | 4 Gi | - |
| **Backend** | 1 | 1000m | 2000m | 2 Gi | 4 Gi | - |
| **Worker** | 3 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **PostgreSQL** | 1 | 250m | 500m | 256 Mi | 512 Mi | 1 Gi |
| **Redis** | 1 | 100m | 200m | 128 Mi | 256 Mi | - |
| **Total** | **7** | **2.85 cores** | **5.7 cores** | **6.4 Gi** | **12.8 Gi** | **1 Gi** |

### Production Configuration (Recommended)

| Component | Replicas | CPU Requests | CPU Limits | Memory Requests | Memory Limits | Storage |
|-----------|----------|--------------|------------|-----------------|---------------|---------|
| **Frontend** | 2 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **Backend** | 3 | 1000m | 2000m | 2 Gi | 4 Gi | - |
| **Worker** | 5 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **PostgreSQL** | 1 | 1000m | 2000m | 2 Gi | 4 Gi | 100 Gi |
| **Redis** | 1 | 500m | 1000m | 1 Gi | 2 Gi | 10 Gi |
| **Total** | **12** | **6.5 cores** | **12 cores** | **11 Gi** | **22 Gi** | **110 Gi** |

### Resource Scaling Guidelines

#### CPU Scaling
- **Frontend**: CPU-intensive during build/compilation, lighter during runtime
- **Backend**: CPU-intensive for AI/ML processing and database operations
- **Worker**: CPU-intensive for parallel task processing
- **Database**: CPU-intensive for complex queries and data processing

#### Memory Scaling
- **Frontend**: High memory usage during Next.js compilation
- **Backend**: High memory usage for AI model loading and data processing
- **Worker**: Moderate memory usage, scales with task complexity
- **Database**: Memory usage scales with data size and query complexity

#### Storage Scaling
- **PostgreSQL**: Scales with data volume (test results, user data)
- **Redis**: Scales with cache size and session data
- **Frontend**: No persistent storage required

### Performance Optimization Tips

1. **SSD Storage**: Use SSD for database storage for better I/O performance
2. **Memory Allocation**: Allocate at least 8GB to Minikube for local development
3. **CPU Cores**: More CPU cores improve parallel processing performance
4. **Worker Scaling**: Increase worker replicas for better task throughput
5. **Database Tuning**: Configure PostgreSQL memory settings based on available RAM

## 📈 Monitoring Resource Usage

### Check Resource Usage
```bash
# View pod resource usage
kubectl top pods -n rhesis

# View node resource usage
kubectl top nodes

# Check resource requests and limits
kubectl describe pods -n rhesis
```

### Common Resource Issues

#### Out of Memory (OOMKilled)
- **Symptoms**: Pods restarting with `OOMKilled` status
- **Solution**: Increase memory limits in `values-local.yaml`
- **Check**: `kubectl describe pod <pod-name> -n rhesis`

#### CPU Throttling
- **Symptoms**: Slow performance, high CPU usage
- **Solution**: Increase CPU limits or requests
- **Check**: `kubectl top pods -n rhesis`

#### Storage Issues
- **Symptoms**: Pods stuck in `Pending` state
- **Solution**: Check available storage and PVC status
- **Check**: `kubectl get pvc -n rhesis`

### Resource Optimization Commands

```bash
# Scale workers for better performance
kubectl scale deployment worker --replicas=5 -n rhesis

# Check resource utilization
kubectl get pods -n rhesis -o wide

# Monitor resource usage in real-time
watch kubectl top pods -n rhesis
```

## 🎯 Deployment Scenarios

### Development Environment
- **Purpose**: Local development and testing
- **Resources**: 8GB RAM, 4 CPU cores
- **Components**: All services with minimal replicas
- **Storage**: 1GB for database
- **Use Case**: Individual developer setup

### Staging Environment
- **Purpose**: Pre-production testing
- **Resources**: 16GB RAM, 8 CPU cores
- **Components**: 2 frontend, 2 backend, 3 workers
- **Storage**: 10GB for database, 1GB for Redis
- **Use Case**: Team testing and validation

### Production Environment
- **Purpose**: Live production deployment
- **Resources**: 32GB+ RAM, 16+ CPU cores
- **Components**: 3+ frontend, 5+ backend, 10+ workers
- **Storage**: 100GB+ for database, 10GB+ for Redis
- **Use Case**: High-availability production service

### Resource Planning Calculator

| Environment | Users | Frontend | Backend | Workers | Total CPU | Total RAM | Storage |
|-------------|-------|----------|---------|---------|-----------|-----------|---------|
| **Development** | 1-2 | 1 | 1 | 3 | 2.85 cores | 6.4 Gi | 1 Gi |
| **Staging** | 5-10 | 2 | 2 | 5 | 4.5 cores | 9 Gi | 11 Gi |
| **Production** | 50+ | 3 | 5 | 10 | 8.5 cores | 18 Gi | 110 Gi |
| **Enterprise** | 500+ | 5 | 10 | 20 | 17 cores | 36 Gi | 500 Gi |

## 🚀 Quick Start

### 1. Build and Load Docker Images

```bash
# Build images (if not already built)
cd apps/frontend && docker build -t rhesis-frontend:latest .
cd ../backend && docker build -t rhesis-backend:latest .
cd ../worker && docker build -t rhesis-worker:latest .

# Load images into Minikube
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest
```

### 2. Apply Prerequisites

```bash
# Apply secrets and configmaps first
kubectl apply -f ../manifests/secrets/
kubectl apply -f ../manifests/configmaps/
```

### 3. Deploy with Helm

```bash
# Option 1: Use the deployment script (recommended)
./deploy-local.sh

# Option 2: Deploy manually
helm install rhesis . --values values-local.yaml --namespace rhesis --create-namespace
```

### 4. Access Your Application

```bash
# Frontend
kubectl port-forward -n rhesis svc/frontend 3000:3000
# Open: http://localhost:3000

# Backend
kubectl port-forward -n rhesis svc/backend 8080:8080
# Open: http://localhost:8080
```

## ⚙️ Configuration

### Values Files

- **`values.yaml`** - Default configuration
- **`values-local.yaml`** - Local development overrides
- **`values-staging.yaml`** - Staging environment (future)
- **`values-prod.yaml`** - Production environment (future)

### Key Configuration Options

```yaml
# Global settings
global:
  environment: "local"
  namespace: "rhesis"
  imagePullPolicy: "Never"  # For local development

# Component enable/disable
backend:
  enabled: true
  replicas: 1
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"

# Database configuration
database:
  enabled: true
  type: "postgresql"
  postgresql:
    persistence:
      enabled: true
      size: "1Gi"
```

## 🔧 Customization

### Override Values

```bash
# Override specific values
helm install rhesis . \
  --set backend.replicas=2 \
  --set database.postgresql.persistence.size=2Gi

# Use custom values file
helm install rhesis . --values my-custom-values.yaml
```

### Environment-Specific Deployments

```bash
# Development
helm install rhesis . --values values-local.yaml

# Staging (future)
helm install rhesis . --values values-staging.yaml

# Production (future)
helm install rhesis . --values values-prod.yaml
```

## 📊 Management

### Check Status

```bash
# Release status
helm status rhesis

# Pod status
kubectl get pods -n rhesis

# All resources
kubectl get all -n rhesis
```

### Upgrade

```bash
# Upgrade with new values
helm upgrade rhesis . --values values-local.yaml

# Upgrade specific values
helm upgrade rhesis . --set backend.replicas=3
```

### Rollback

```bash
# List history
helm history rhesis

# Rollback to previous version
helm rollback rhesis 1
```

### Uninstall

```bash
# Remove the release
helm uninstall rhesis

# Remove namespace (optional)
kubectl delete namespace rhesis

# Shutdown all pods in the namespace
kubectl scale deployment --all --replicas=0 -n rhesis
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Image Pull Errors
```bash
# Error: ErrImageNeverPull
# Solution: Load images into Minikube
minikube image load rhesis-frontend:latest
```

#### 2. Missing Secrets/ConfigMaps
```bash
# Apply prerequisites first
kubectl apply -f ../manifests/secrets/
kubectl apply -f ../manifests/configmaps/
```

#### 3. Pod Not Ready
```bash
# Check pod details
kubectl describe pod -n rhesis <pod-name>

# Check logs
kubectl logs -n rhesis <pod-name>
```

### Debug Commands

```bash
# Validate chart
helm lint .

# Template rendering (dry-run)
helm template rhesis . --values values-local.yaml

# Check values
helm get values rhesis
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───►│    Backend      │───►│   PostgreSQL    │
│   (Next.js)     │    │   (FastAPI)     │    │   Port: 5432    │
│   Port: 3000    │    │   Port: 8080    │    └─────────────────┘
└─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │     Redis       │◄───│     Worker      │
                       │   Port: 6379    │    │   (Celery)      │
                       └─────────────────┘    │   Port: 8080    │
                                              └─────────────────┘
```

**Component Details:**
- **Frontend** (Next.js) - Port 3000
- **Backend** (FastAPI) - Port 8080  
- **Worker** (Celery) - Port 8080
- **PostgreSQL** - Port 5432
- **Redis** - Port 6379

## 🔮 Future Enhancements

- **Ingress support** - External access configuration
- **Monitoring stack** - Prometheus and Grafana integration
- **Network policies** - Security and access control
- **RBAC configuration** - Role-based access control
- **External databases** - Support for managed database services
- **Auto-scaling** - Horizontal Pod Autoscaler (HPA)

## 📚 References

- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Rhesis Project](https://github.com/your-org/rhesis)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `helm lint .` and `helm template .`
5. Submit a pull request

## 📄 License

This project is licensed under the same license as the Rhesis project.
