# Kubernetes Management Guide

A friendly guide to managing your Rhesis Kubernetes deployment without the fear! 🚀

## Quick Start

The `k8s-deploy.sh` script is your one-stop tool for managing everything Kubernetes-related.

```bash
./k8s-deploy.sh <command> [options]
```

## Common Workflows

### 🔐 Configure Secrets (before first deploy)

```bash
./generate-secrets.sh
```

Creates `manifests/secrets/rhesis-secrets.yaml` from the example template. The template mirrors
`docker-compose.yml`'s approach: most values already have a working local default baked in
(`APP_DB_PASS`, `REDIS_PASSWORD`, `STORAGE_SERVICE_URI`, ...) or ship as a safely-disabled empty
string — a Kubernetes Secret must be valid base64 for every key, so unlike a `.env` file there's
no "just leave it blank" placeholder text. Only four secrets have no safe default:
`DB_ENCRYPTION_KEY`, `JWT_SECRET_KEY`, `NEXTAUTH_SECRET`, `SESSION_SECRET_KEY` — the script
generates these. Re-running it is safe; it only fills keys still blank, never overwrites values
you've already set, and blanks out any stale `<BASE64_ENCODED_*>` placeholder text left over from
an older copy of the file (which isn't valid base64 and would make `kubectl apply` reject the
whole secret).

For anything else you want to configure (`RHESIS_API_KEY`, `OPENAI_API_KEY`, `SMTP_*`,
`GOOGLE_CLIENT_*`, ...), encode it yourself and paste the result into
`manifests/secrets/rhesis-secrets.yaml`:

```bash
./generate-secrets.sh encode "your-actual-value"
```

Non-sensitive configuration (URLs, model names, ports) lives separately in
`manifests/configmaps/rhesis-config.yaml` — copy it from `rhesis-config.yaml.example` and edit
directly, no encoding needed.

**When to use**: Once, before your first deploy. Both files are gitignored — never commit them.

### 🆕 First Time Setup

```bash
./k8s-deploy.sh reset
```

This does a complete fresh installation:
- Deletes old images and volumes
- Rebuilds all Docker images
- Loads them into Minikube
- Applies secrets/configmaps and deploys everything

**When to use**: First deployment (after configuring secrets above), or when things are completely
broken and you want to start over. This wipes your database and Redis data — it's the only
command that does.

### 🔁 Apply Changes Without Rebuilding

```bash
./k8s-deploy.sh apply
```

Applies the namespace, secrets, configmaps, and Helm release (installing it if it doesn't exist
yet), then restarts every service so it actually picks up whatever changed — using whatever
images are already loaded into Minikube, no Docker build step. **Keeps your database data.**

**When to use**: You edited `values-local.yaml`, `rhesis-config.yaml`, or `rhesis-secrets.yaml`;
Minikube restarted and the deployment needs re-applying; or anything just needs reapplying and you
haven't changed application code.

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

Bounces one service's pods — nothing else. No manifests re-applied, no Helm, no images reloaded;
the new pod just picks up whatever image/config the deployment already has. Useful for a
stuck/crashed pod. If you actually changed config or secrets, use `apply` instead — `restart`
alone won't pick those up.

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

### Scenario 3: I changed values-local.yaml, rhesis-config.yaml, or rhesis-secrets.yaml

```bash
./k8s-deploy.sh apply
./k8s-deploy.sh status
```

### Scenario 4: Backend won't start, need to debug

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

### Scenario 5: Everything is broken, start over

```bash
./k8s-deploy.sh reset
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
./k8s-deploy.sh reset
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

