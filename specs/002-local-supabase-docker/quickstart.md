# Quickstart Guide: Local Supabase Deployment

**Feature**: 002-local-supabase-docker
**Date**: 2026-01-01
**Estimated Time**: 15-30 minutes

## Overview

This guide will walk you through deploying the CortexReview platform with a self-hosted Supabase instance on a local Ubuntu server using Docker Compose. No external Supabase Cloud account required.

---

## Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4GB | 8GB |
| CPU Cores | 2 | 4 |
| Disk Space | 20GB | 50GB |
| Operating System | Ubuntu 20.04/22.04 LTS | Ubuntu 22.04 LTS |

### Software Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- Basic familiarity with command line

### Verification

```bash
# Check Docker version
docker --version
# Expected: Docker version 20.10.0 or higher

# Check Docker Compose version
docker compose version
# Expected: Docker Compose version v2.0.0 or higher

# Check Git
git --version
# Expected: git version 2.x.x or higher
```

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/bestK/gitea-ai-codereview.git
cd gitea-ai-codereview

# Checkout the feature branch
git checkout 002-local-supabase-docker
```

---

## Step 2: Configure Environment Variables

### Create .env File

```bash
# Copy example environment file
cp .env.example .env

# Edit with your favorite editor
nano .env
```

### Required Variables

```bash
# === Supabase Configuration ===
POSTGRES_PASSWORD=your_secure_password_here_min_16_chars
JWT_SECRET=your_jwt_secret_here_min_64_chars
ANON_KEY=your_anon_key_here_generate_with_jwt_secret
SERVICE_ROLE_KEY=your_service_role_key_here_generate_with_jwt_secret
POSTGRES_DB=supabase

# === LLM Configuration ===
LLM_API_KEY=your_openai_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
EMBEDDING_MODEL=text-embedding-3-small

# === Git Platform Configuration ===
PLATFORM=gitea
GITEA_HOST=your.gitea.server
GITEA_TOKEN=your_gitea_token_here

# === Celery Configuration ===
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# === Observability (Optional) ===
ENABLE_PROMETHEUS=true
ENABLE_GRAFANA=true
LOG_LEVEL=INFO
```

### Generate Secure Secrets

```bash
# Generate JWT_SECRET (64 characters)
openssl rand -base64 64

# Generate ANON_KEY from JWT_SECRET
# Use: https://supabase.com/docs/guides/platform/custom-jwt
# Or use Supabase CLI: supabase generate anon-key

# Generate SERVICE_ROLE_KEY from JWT_SECRET
# Use: https://supabase.com/docs/guides/platform/custom-jwt
# Or use Supabase CLI: supabase generate service-role-key

# Generate POSTGRES_PASSWORD (16 characters)
openssl rand -base64 16
```

---

## Step 3: Start Services

### Start All Services

```bash
# Start all services in detached mode
docker compose up -d

# Expected output:
# Creating network "cortexreview-network"
# Creating volume "cortexreview-redis-data"
# Creating volume "cortexreview-supabase-db-data"
# Creating cortexreview-redis ... done
# Creating cortexreview-supabase-db ... done
# Creating cortexreview-api ... done
# Creating cortexreview-worker ... done
```

### Verify Services Running

```bash
# Check all containers are healthy
docker compose ps

# Expected output (State should be "Up" and "Healthy"):
# NAME                          STATE                     STATUS
# cortexreview-api              Up                        Healthy
# cortexreview-worker           Up                        Healthy
# cortexreview-redis            Up                        Healthy
# cortexreview-supabase-db      Up                        Healthy
```

### Monitor Startup Logs

```bash
# View logs for all services
docker compose logs -f

# View logs for specific service
docker logs cortexreview-supabase-db -f
```

---

## Step 4: Verify Database Initialization

### Connect to Database

```bash
# Connect to PostgreSQL
docker exec -it cortexreview-supabase-db psql -U postgres -d supabase
```

### Run Verification Queries

```sql
-- List all tables
\dt public.*

-- Expected output:
-- knowledge_base
-- learned_constraints
-- feedback_audit_log
-- schema_migrations

-- Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Expected output: One row with extname='vector'

-- Test match_knowledge function
SELECT * FROM match_knowledge(
  '[0.1, 0.2]'::vector || array_fill(0.0, ARRAY[1534]),
  0.75,
  3
);

-- Expected output: Empty table (no error)

-- Exit psql
\q
```

---

## Step 5: Access Supabase Studio (Optional)

### Start Studio Container

```bash
# Start Studio (development profile)
docker compose --profile development up -d supabase-studio

# Verify Studio running
docker ps | grep studio
```

### Access Studio Dashboard

1. Open browser: http://localhost:8000
2. Login with credentials:
   - Email: `admin@localhost.local`
   - Password: (from `STUDIO_DEFAULT_PASSWORD` environment variable)
   - **SECURITY WARNING**: The default password `admin` should **NEVER** be used in production.
     Change immediately via `STUDIO_DEFAULT_PASSWORD` in your `.env` file.
3. Navigate to: Table Editor
4. Verify tables visible: knowledge_base, learned_constraints, feedback_audit_log

### Stop Studio (Production)

```bash
# Stop Studio (not needed for production)
docker compose stop supabase-studio

# Remove Studio container
docker compose rm -f supabase-studio
```

---

## Step 6: Configure Webhook Integration

### Gitea Webhook Configuration

1. Login to your Gitea server
2. Navigate to repository settings
3. Click "Webhooks" → "Add Webhook"
4. Configure webhook:
   - **Target URL**: `http://your-server:3008/codereview`
   - **HTTP Method**: POST
   - **Content Type**: application/json
   - **Secret**: (generate random secret)
   - **Events**: Push Events
5. Save webhook

### Update Environment Variables

```bash
# Add webhook secret to .env
echo "PLATFORM_GITEA_WEBHOOK_SECRET=your_webhook_secret_here" >> .env

# Restart API to apply changes
docker compose restart api
```

---

## Step 7: Test the System

### Trigger Test Review

```bash
# Push a commit to the configured repository
git commit --allow-empty -m "Test code review"
git push origin main

# Or manually trigger via API
curl -X POST http://localhost:3008/test \
  -H "Content-Type: application/json" \
  -d '{"diff": "print(\"hello world\")"}'
```

### Verify Processing

```bash
# Check worker logs
docker logs cortexreview-worker --tail 50

# Check API logs
docker logs cortexreview-api --tail 50

# Verify task completed
docker exec cortexreview-redis redis-cli LLEN celery
```

---

## Step 8: Backup Setup (Recommended)

### Create Backup Directory

```bash
mkdir -p ./backups
chmod 700 ./backups
```

### Configure Automated Backups

```bash
# Copy backup script (if not already present)
cp scripts/backup_supabase.sh ./scripts/

# Make executable
chmod +x ./scripts/backup_supabase.sh

# Test backup
./scripts/backup_supabase.sh

# Verify backup created
ls -lh ./backups/
```

### Schedule Weekly Backups (Optional)

```bash
# Install cron if not present
sudo apt-get install cron

# Add cron job
sudo bash -c 'cat > /etc/cron.d/cortexreview-backup << EOF
# Weekly backup every Sunday at 2 AM
0 2 * * 0 root /path/to/gitea-ai-codereview/scripts/backup_supabase.sh >> /var/log/supabase_backup.log 2>&1
EOF'

# Verify cron job
sudo crontab -l
```

---

## Troubleshooting

### Containers Won't Start

**Symptom**: `docker compose up -d` fails

**Solution**:
```bash
# Check Docker is running
sudo systemctl status docker

# Check for port conflicts
sudo netstat -tulpn | grep -E '(3000|3008|5432|6379|8000|9090)'

# Check logs
docker compose logs
```

---

### Database Initialization Fails

**Symptom**: Supabase container exits immediately

**Solution**:
```bash
# Check logs for error
docker logs cortexreview-supabase-db

# Common issue: Missing environment variables
# Verify .env file has required variables:
docker compose config | grep POSTGRES_PASSWORD

# Re-create database volume (WARNING: destroys data)
docker compose down
docker volume rm cortexreview-supabase-db-data
docker compose up -d
```

---

### API Cannot Connect to Database

**Symptom**: API logs show "connection refused" to supabase-db

**Solution**:
```bash
# Verify containers on same network
docker network inspect cortexreview-network

# Verify database container running
docker ps | grep supabase-db

# Test connection from API container
docker exec cortexreview-api ping supabase-db -c 3

# Restart API container
docker compose restart api
```

---

### Out of Memory

**Symptom**: Container killed with OOM error

**Solution**:
```bash
# Check system memory
free -h

# Disable optional services (Studio)
docker compose stop supabase-studio

# Reduce worker concurrency
# Add to .env: CELERY_WORKER_CONCURRENCY=2

# Restart worker
docker compose restart worker
```

---

## Advanced Configuration

### Resource Limits

```yaml
# Add to docker-compose.yml for each service:
services:
  supabase-db:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Custom PostgreSQL Configuration

```yaml
# Add to supabase-db service:
services:
  supabase-db:
    command:
      - postgres
      - -c
      - shared_buffers=2GB
      - -c
      - max_connections=200
```

### Disable Optional Services

```bash
# Start without Studio
docker compose up -d
docker compose --profile observability up -d prometheus grafana

# Start core services only (no observability)
docker compose up -d api worker redis supabase-db
```

---

## Migration from External Supabase

If you have an existing external Supabase deployment, see [contracts/migration-procedures.md](contracts/migration-procedures.md) for detailed migration instructions.

### Quick Migration Summary

```bash
# 1. Export from external Supabase
export EXTERNAL_SUPABASE_URL="xyz.supabase.co"
export EXTERNAL_SUPABASE_PASSWORD="your-service-role-key"
./scripts/export_from_external.sh

# 2. Import to local Supabase
./scripts/import_to_local.sh

# 3. Update application .env to use local
# (Already configured via docker-compose)

# 4. Restart services
docker compose restart api worker
```

---

## Performance Tuning

### Database Tuning

```sql
-- Connect to database
docker exec -it cortexreview-supabase-db psql -U postgres -d supabase

-- Increase shared_buffers (restart required)
ALTER SYSTEM SET shared_buffers = '2GB';

-- Increase work_mem for large sorts
ALTER SYSTEM SET work_mem = '256MB';

-- Rebuild indexes with more lists
DROP INDEX idx_kb_vector;
CREATE INDEX idx_kb_vector
  ON public.knowledge_base
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 200);

-- Apply changes (requires restart)
SELECT pg_reload_conf();
```

---

### Worker Tuning

```bash
# Increase worker concurrency
echo "CELERY_WORKER_CONCURRENCY=8" >> .env

# Increase task time limit
echo "CELERY_TASK_TIME_LIMIT=600" >> .env

# Restart worker
docker compose restart worker
```

---

## Security Hardening

### Firewall Configuration

```bash
# Configure UFW (Uncomplicated Firewall)
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow API port
sudo ufw allow 3008/tcp

# Allow Studio (development only)
sudo ufw allow 8000/tcp

# Deny database port (external access)
sudo ufw deny 5432/tcp

# Check status
sudo ufw status
```

### SSL/TLS Termination

**Note**: For production, deploy reverse proxy (Nginx/Caddy) with SSL.

See: [docs/ssl-setup.md](../../docs/ssl-setup.md) (not included in this feature)

---

## Next Steps

1. **Monitor system**: Check Grafana dashboards (http://localhost:3000)
2. **Review logs**: `docker logs cortexreview-api -f`
3. **Test review flow**: Push a commit and verify review posted
4. **Configure backups**: Ensure weekly backups scheduled
5. **Read documentation**:
   - [data-model.md](data-model.md) - Database schema
   - [contracts/supabase-initialization.md](contracts/supabase-initialization.md) - Initialization
   - [contracts/backup-procedures.md](contracts/backup-procedures.md) - Backups

---

## Support

### Getting Help

- **Documentation**: [docs/](../../docs/)
- **Issues**: [GitHub Issues](https://github.com/bestK/gitea-ai-codereview/issues)
- **Logs**: Check container logs first
- **Health Check**: `docker compose ps`

### Common Commands

```bash
# View logs
docker compose logs -f [service_name]

# Restart service
docker compose restart [service_name]

# Stop all services
docker compose down

# Start all services
docker compose up -d

# Rebuild containers
docker compose up -d --build

# Remove all data (WARNING: destructive)
docker compose down -v
```

---

**Congratulations!** Your local Supabase deployment is now running. The CortexReview platform is fully operational with no external dependencies for core functionality.
