# Kubernetes Management Guide

A friendly guide to managing your Rhesis Kubernetes deployment without the fear! 🚀

## Quick Start

The `k8s-deploy.sh` script is your one-stop tool for managing everything Kubernetes-related.

```bash
./k8s-deploy.sh <command> [options]
```

## Common Workflows

### 🆕 First Time Setup

```bash
./k8s-deploy.sh clean
```

This does a complete fresh installation:
- Deletes old images and volumes
- Rebuilds all Docker images
- Loads them into Minikube
- Deploys everything

**When to use**: First deployment, or when things are completely broken and you want to start fresh.

### 📝 Changed Configuration Files Only

```bash
./k8s-deploy.sh update
```

Use this when you've modified:
- `values-local.yaml` (resource limits, replicas, env vars)
- `rhesis-config.yaml` (ConfigMap values)
- `rhesis-secrets.yaml` (Secret values)

**What it does**: Updates Helm release with new values, no image rebuild, **keeps your database data**.

### 🔨 Changed Application Code

```bash
# Rebuild all services
./k8s-deploy.sh rebuild

# Rebuild specific service only
./k8s-deploy.sh rebuild backend
./k8s-deploy.sh rebuild frontend
./k8s-deploy.sh rebuild worker
./k8s-deploy.sh rebuild chatbot
./k8s-deploy.sh rebuild docs
```

**What it does**: 
- Deletes old images
- Rebuilds Docker images
- Loads into Minikube
- Restarts the service(s)
- **Keeps your database data**

### 🔄 Quick Restart of a Service

```bash
./k8s-deploy.sh restart backend
./k8s-deploy.sh restart frontend
```

Just restarts the pods without rebuilding. Useful for applying changes after a rebuild.

## Debugging & Monitoring

### 📊 Check Status

```bash
./k8s-deploy.sh status
```

Shows:
- All pods and their status
- All services
- Persistent volumes
- Helm releases

### 📋 View Logs

```bash
# View last 100 lines
./k8s-deploy.sh logs backend

# Follow logs in real-time (like tail -f)
./k8s-deploy.sh logs backend --follow
./k8s-deploy.sh logs frontend -f

# Other services
./k8s-deploy.sh logs worker --follow
./k8s-deploy.sh logs chatbot -f
```

**Pro tip**: Use `--follow` or `-f` to watch logs live. Press `Ctrl+C` to exit.

### 🐚 Shell into a Pod

```bash
./k8s-deploy.sh shell backend
./k8s-deploy.sh shell frontend
```

Opens an interactive shell inside the container. Great for debugging!

**Commands you can run inside**:
- `ls`, `cd`, `cat`, etc.
- `env` - see environment variables
- `ps aux` - see running processes
- `exit` - close the shell

### 🗄️ Database Access

```bash
./k8s-deploy.sh db
```

Opens a PostgreSQL shell connected to your database.

**Useful SQL commands**:
```sql
\l              -- List databases
\dt             -- List tables
\d+ table_name  -- Describe table
SELECT * FROM users LIMIT 10;
\q              -- Quit
```

### 🔴 Redis Access

```bash
./k8s-deploy.sh redis
```

Opens a Redis CLI.

**Useful Redis commands**:
```
KEYS *          -- List all keys
GET key_name    -- Get a value
FLUSHALL        -- Clear everything (careful!)
exit            -- Quit
```

## Networking

### 🌐 Port Forwarding

```bash
# Show port forward commands
./k8s-deploy.sh port-forward

# Forward specific service
./k8s-deploy.sh port-forward frontend   # http://localhost:3000
./k8s-deploy.sh port-forward backend    # http://localhost:8080
./k8s-deploy.sh port-forward chatbot    # http://localhost:8083
./k8s-deploy.sh port-forward docs       # http://localhost:3001

# Start all in background
./k8s-deploy.sh port-forward all &
```

**To stop all port forwards**:
```bash
killall kubectl
```

## Scaling

### 📏 Scale Services

```bash
# Scale to 3 replicas
./k8s-deploy.sh scale backend 3

# Scale down to 0 (stop without deleting)
./k8s-deploy.sh scale frontend 0

# Scale back up
./k8s-deploy.sh scale frontend 1
```

## Typical Development Workflows

### Scenario 1: I changed some Python code in backend

```bash
./k8s-deploy.sh rebuild backend
./k8s-deploy.sh logs backend --follow
```

### Scenario 2: I changed React components in frontend

```bash
./k8s-deploy.sh rebuild frontend
./k8s-deploy.sh logs frontend --follow
```

### Scenario 3: I increased memory limits in values-local.yaml

```bash
./k8s-deploy.sh update
./k8s-deploy.sh status
```

### Scenario 4: I added a new environment variable to ConfigMap

```bash
# First apply the ConfigMap manually
kubectl apply -f manifests/configmaps/rhesis-config.yaml -n rhesis

# Then update and restart
./k8s-deploy.sh update
```

### Scenario 5: Backend won't start, need to debug

```bash
# Check status
./k8s-deploy.sh status

# View logs
./k8s-deploy.sh logs backend

# Shell into pod if it's running
./k8s-deploy.sh shell backend

# Check database connection
./k8s-deploy.sh db
```

### Scenario 6: Everything is broken, start over

```bash
./k8s-deploy.sh clean
```

## Tips & Tricks

### 🎯 Quick Status Check

Create an alias in your `~/.zshrc` or `~/.bashrc`:

```bash
alias k8s-status='kubectl get pods -n rhesis'
alias k8s-logs='kubectl logs -n rhesis -f'
```

### 🔥 Hot Reload for Frontend Development

For faster frontend development, consider using:

```bash
# Scale down K8s frontend
./k8s-deploy.sh scale frontend 0

# Run frontend locally with hot reload
cd apps/frontend
npm run dev
```

Then you can edit React components and see changes instantly without rebuilding Docker images!

### 💡 Viewing Multiple Logs at Once

Use `tmux` or multiple terminal tabs:

```bash
# Terminal 1
./k8s-deploy.sh logs backend --follow

# Terminal 2
./k8s-deploy.sh logs worker --follow

# Terminal 3
./k8s-deploy.sh logs chatbot --follow
```

### 🧹 Clean Up Minikube Resources

If you want to completely reset Minikube (nuclear option):

```bash
minikube delete
minikube start --driver=docker --memory=8192 --cpus=2
./k8s-deploy.sh clean
```

## Troubleshooting

### Pod is in CrashLoopBackOff

```bash
# Check the logs
./k8s-deploy.sh logs <service>

# Check pod events
kubectl describe pod -n rhesis <pod-name>

# Try rebuilding
./k8s-deploy.sh rebuild <service>
```

### ImagePullBackOff errors

This usually means the image wasn't loaded into Minikube:

```bash
./k8s-deploy.sh rebuild <service>
```

### Database connection errors

```bash
# Check if postgres is running
./k8s-deploy.sh status

# Connect to verify credentials
./k8s-deploy.sh db

# Check backend env vars
./k8s-deploy.sh shell backend
env | grep SQLALCHEMY
```

### Out of disk space in Minikube

```bash
# Check Minikube disk usage
minikube ssh
df -h

# Clean up old images
docker system prune -a

# If really stuck, delete and recreate
minikube delete
minikube start --driver=docker --memory=8192 --cpus=2
```

## Help

```bash
./k8s-deploy.sh help
```

Shows all available commands with examples.

---

**Remember**: Kubernetes is your friend, not your enemy! 🤝 Use these tools to make your development experience smooth and enjoyable.

