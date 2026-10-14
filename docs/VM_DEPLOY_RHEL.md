# Red Hat Enterprise Linux (RHEL 8 / 9) Deployment Guide

This guide covers production deployment of **Mobileum Horizon (Renewals Intelligence)** on a RHEL VM using two supported paths:
1. **No-Docker Path (Recommended for Enterprise VMs)**: Systemd + Python Virtualenv + Nginx + PostgreSQL
2. **Docker Path**: Docker Engine + Docker Compose

---

## 1. System Prerequisites & RHEL Packages

Enable standard enterprise repositories and install system packages:

```bash
# Update system
sudo dnf update -y

# Install Python 3.11+, Git, PostgreSQL client, and Nginx
sudo dnf install -y git python3.11 python3.11-pip python3.11-devel \
    postgresql-server postgresql-contrib nginx tar curl gcc
```

---

## 2. PostgreSQL Setup on RHEL

Initialize and start PostgreSQL on the VM:

```bash
# Initialize database cluster
sudo postgresql-setup --initdb

# Enable and start PostgreSQL service
sudo systemctl enable --now postgresql

# Create application user and database
sudo -u postgres psql << 'EOF'
CREATE USER renewals_user WITH PASSWORD 'StrongSecurePassword123!';
CREATE DATABASE renewals OWNER renewals_user;
GRANT ALL PRIVILEGES ON DATABASE renewals TO renewals_user;
\q
EOF
```

> [!NOTE]
> Ensure `/var/lib/pgsql/data/pg_hba.conf` allows password authentication (`md5` or `scram-sha-256`) for local TCP or socket connections:
> ```text
> local   all             all                                     scram-sha-256
> host    all             all             127.0.0.1/32            scram-sha-256
> ```
> Reload Postgres after changing `pg_hba.conf`: `sudo systemctl reload postgresql`.

---

## 3. Path A: No-Docker Deployment (venv + systemd + nginx)

### Step 1: Create application user and directory
```bash
sudo useradd -r -s /bin/bash -d /opt/renewals renewals
sudo mkdir -p /opt/renewals
sudo chown -R renewals:renewals /opt/renewals
```

### Step 2: Clone repository and configure virtualenv
```bash
cd /opt/renewals
sudo -u renewals git clone https://github.com/RishithaThoka/renewals_data.git .

# Create Python virtual environment
sudo -u renewals python3.11 -m venv venv
sudo -u renewals ./venv/bin/pip install --upgrade pip
sudo -u renewals ./venv/bin/pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy the template and fill in your production credentials:
```bash
sudo -u renewals cp .env.example .env
sudo -u renewals chmod 600 .env
```
Edit `/opt/renewals/.env`:
```ini
DATABASE_URL=postgresql+psycopg://renewals_user:StrongSecurePassword123!@localhost:5432/renewals
ADMIN_PASSWORD=YourStrongAdminPasswordHere
ADMIN_SECRET_KEY=e839201bc89a7465f... # 64-char hex key
ENVIRONMENT=production
COOKIE_SECURE=false # Set true if terminating SSL
CORS_ORIGINS=["http://localhost","http://YOUR_SERVER_IP"]
```

> [!IMPORTANT]
> If your database password contains special characters (like `@`, `#`, `/`), they must be URL-encoded (e.g., `@` becomes `%40`).

### Step 4: Verify Database Connection & Run Migrations
```bash
# Run connection diagnostic script
sudo -u renewals ./venv/bin/python scripts/check_db.py

# Run Alembic migrations to head
sudo -u renewals ./venv/bin/alembic upgrade head
```

### Step 5: (Optional) Migrate Existing SQLite Data
If migrating from an earlier SQLite setup:
```bash
sudo -u renewals ./venv/bin/python scripts/copy_sqlite_to_postgres.py --sqlite renewals.db
```

### Step 6: Build Frontend Static Bundle
```bash
# Install Node.js (v20+ LTS)
sudo dnf module enable -y nodejs:20
sudo dnf install -y nodejs

cd /opt/renewals/frontend
sudo -u renewals npm ci
sudo -u renewals npm run build
```

### Step 7: Configure and Start Systemd Service
```bash
sudo cp /opt/renewals/deploy/renewals.service /etc/systemd/system/renewals.service
sudo systemctl daemon-reload
sudo systemctl enable --now renewals.service

# Verify service is running
sudo systemctl status renewals.service
curl -s http://127.0.0.1:8000/api/health
```

### Step 8: Configure Nginx & Firewall
```bash
sudo cp /opt/renewals/deploy/nginx-renewals.conf /etc/nginx/conf.d/renewals.conf

# Adjust SELinux for Nginx reverse proxying
sudo setsebool -P httpd_can_network_connect 1

# Test Nginx syntax and start
sudo nginx -t
sudo systemctl enable --now nginx

# Open HTTP/HTTPS in firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Step 9: Configure Automated Daily Backups
Add a cron job to back up PostgreSQL daily at 02:00 AM:
```bash
sudo chmod +x /opt/renewals/deploy/backup_db.sh
sudo crontab -u renewals -l 2>/dev/null | { cat; echo "0 2 * * * /opt/renewals/deploy/backup_db.sh >> /opt/renewals/backups/backup.log 2>&1"; } | sudo crontab -u renewals -
```

---

## 4. Path B: Docker Deployment (Docker Compose)

### Step 1: Install Docker Engine on RHEL
```bash
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

### Step 2: Configure .env and Start Containers
```bash
cd /opt/renewals
cp .env.example .env
# Set DATABASE_URL and secrets in .env

docker compose up -d --build
```

### Step 3: Verify Health
```bash
curl -s http://localhost/api/health
docker compose logs -f app
```

---

## 5. Ongoing Updates (`deploy.sh`)

For subsequent releases on the VM:
```bash
cd /opt/renewals
sudo chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh
```
