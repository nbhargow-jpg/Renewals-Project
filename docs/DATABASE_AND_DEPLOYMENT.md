# Database Architecture & Production Deployment

This document provides a comprehensive operational guide for database management, migrations, deployment architectures, daily ingestion workflows, and disaster recovery for Mobileum Horizon (Renewals Intelligence Platform).

---

## 1. Database Architecture & Table Design

### Daily Snapshot Model (Point-in-Time Copies)
Mobileum Horizon retains one year of daily snapshots (~365 snapshots). Rather than mutable row-level overwrites, each daily ingestion creates an isolated `upload_snapshots` record and stores a **full copy of all opportunity deal rows** as of that date in `opportunities`.

#### Primary Tables:
1. **`upload_snapshots`**:
   - Stores snapshot metadata (`snapshot_date`, `quarter_name`, `fiscal_year`, `total_acv`, `deal_count`, `active`).
   - Ensures `snapshot_date` uniqueness (or overwrite flag `replace=true`).
2. **`uploaded_files`**:
   - Stores file metadata and cryptographic SHA-256 hash (`sha256_hash`) for duplicate file detection and idempotency.
3. **`opportunities`**:
   - Complete deal records linked to a `snapshot_id`.
   - Constrained by `uq_opp_snapshot_opportunity_id` (`snapshot_id`, `opportunity_id_18`).
   - Indexed for low-latency queries across:
     - `(snapshot_id, sales_type, fiscal_period)`
     - `(snapshot_id, revised_sub_region)`
     - `(snapshot_id, forecast_category)`
     - `(snapshot_id, approval_status)`
   - Uses native `JSONB` on PostgreSQL (and `JSON` on SQLite) for flexible metadata in `extra_attributes`.
4. **`change_logs` & `forecast_movement_log`**:
   - Tracks deal field changes and forecast movements across consecutive daily snapshots.
5. **`daily_summary`**:
   - Aggregated metrics per snapshot.

---

## 2. SQLite vs. PostgreSQL Modes

The system operates seamlessly in dual-dialect mode:

| Dimension | SQLite Mode | PostgreSQL Mode |
|---|---|---|
| **Primary Use Case** | Local offline development & fast unit tests | Multi-user VM deployment, production Docker |
| **Engine Configuration** | `connect_args={"check_same_thread": False}`, `StaticPool` in tests | Connection pooling (`pool_size=10, max_overflow=20`), `pool_pre_ping=True` |
| **JSON Storage** | Standard SQLite TEXT/JSON | Native binary `JSONB` with indexing support |
| **Concurrency** | Single-writer serialized | Full ACID multi-client MVCC |
| **Startup Behavior** | Fallback to `Base.metadata.create_all` if unmigrated | Strict fail-fast on migration failure (`alembic upgrade head`) |

### Switching via `DATABASE_URL`
Configure the database dialect through the `DATABASE_URL` environment variable:

- **Local SQLite (Default)**:
  ```bash
  DATABASE_URL=sqlite:///./renewals.db
  ```
- **PostgreSQL (Local / Container)**:
  ```bash
  DATABASE_URL=postgresql://renewals_user:secret_password@localhost:5432/renewals_prod
  ```
  *(Note: The system automatically normalizes `postgres://` or `postgresql://` URIs to the high-performance `postgresql+psycopg://` driver).*

---

## 3. Database Schema Migrations (Alembic)

Schema migrations are governed by Alembic.

### Applying Migrations
```bash
alembic upgrade head
```
*Note: In Docker containers, `alembic upgrade head` executes automatically during container startup before the web worker launches.*

### Generating a New Migration
When modifying model declarations in `backend/models/*.py`:
```bash
alembic revision --autogenerate -m "describe_change"
```
Review the newly generated file in `alembic/versions/` and verify the `upgrade()` and `downgrade()` operations.

### Rolling Back a Migration
To roll back the most recent migration:
```bash
alembic downgrade -1
```
To roll back to a specific revision:
```bash
alembic downgrade <revision_id>
```

---

## 4. Daily Upload & Ingestion Workflow

1. **Upload Session Initiation**:
   - File uploads land in temporary persistent disk storage under `scratch/upload_sessions/` (or Docker `UPLOAD_DIR`), expiring after 24 hours.
2. **Pre-flight Validation**:
   - Checks SHA-256 hashes against existing uploads to prevent accidental re-imports.
   - Validates mandatory columns (`opportunity_id_18`, `forecast_acv_amount`, `forecast_category`, `close_date`).
   - Scans and reports warnings for unmapped or blank regions.
3. **Atomic Database Commit**:
   - Execution occurs within a single database transaction. If an error occurs midway, `db.rollback()` executes, guaranteeing that zero orphaned deals or corrupted snapshots are persisted.
4. **Active Snapshot Resolution**:
   - The newest snapshot date is set as the active reference, updating comparisons (`yesterday` and `last_week`).

---

## 5. Backup & Disaster Recovery

### Automated PostgreSQL Backups (`scripts/backup.sh`)
Uses `pg_dump` with custom archive format (`-F c`), capturing all data, schema, indexes, and constraints.

#### Manual Execution:
```bash
DB_HOST=localhost DB_PORT=5432 DB_USER=renewals_user DB_NAME=renewals_prod ./scripts/backup.sh
```

#### Automated Cron Configuration:
On the host Linux VM, schedule daily automated backups at 02:00 AM:
```cron
0 2 * * * cd /opt/renewals && ./scripts/backup.sh >> /var/log/renewals_backup.log 2>&1
```

#### 30-Day Retention Policy:
The script automatically cleans up archives older than 30 days, retaining the latest 30 daily snapshots.

### Restoring from Backup (`scripts/restore.sh`)
To restore an archived backup into a target database:
```bash
./scripts/restore.sh ./backups/renewals_prod_YYYYMMDD_HHMMSS.dump renewals_prod
```
The script performs a clean restore using:
```bash
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists -v "$BACKUP_FILE"
```

---

## 6. Docker Container Deployment

Deploy the entire stack with Docker Compose:

```bash
# 1. Prepare environment variables
cp .env.example .env
# Edit .env with secure passwords

# 2. Build and launch services
docker compose up --build -d

# 3. Verify health status
docker compose ps
```
The application is served at `http://localhost`, with Nginx reverse-proxying `/api` requests to the FastAPI backend and serving static assets for the React frontend.

---

## 7. Admin Authentication & Production Security (Addendum D)

All mutating endpoints (`/api/snapshots/validate`, `/commit`, `/upload`, `DELETE /snapshots/{id}`, and direct routes) are strictly gated behind administrator credentials. Public read routes remain open for analytics consumption.

### Security Configurations in `.env`:

```bash
# 1. Administrator Password (Mandatory for write routes)
# If unset or empty, all write operations fail-safe with 403 Forbidden.
ADMIN_PASSWORD=your_strong_admin_password_here

# 2. Cryptographic Token Signing Key (Mandatory)
# Generate with:
# python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_SECRET_KEY=4a92f80c653d9e82103f5b7a19283746c0b9a8f7e6d5c4b3a291807f6e5d4c3b

# 3. Environment & Cookie Security
# When ENVIRONMENT=production, cookies default to Secure (HTTPS only).
ENVIRONMENT=production

# Explicit override for cookie Secure flag (set to true behind HTTPS reverse proxy):
COOKIE_SECURE=true
```

### Production HTTPS Requirements:
- When hosted on a VM or cloud environment, **HTTPS is strictly required**.
- Nginx or your cloud load balancer must terminate TLS and forward requests with `X-Forwarded-Proto: https`.
- `COOKIE_SECURE=true` ensures the `admin_token` HttpOnly cookie is never transmitted over unencrypted plaintext HTTP connections.
- If `ADMIN_PASSWORD` or `ADMIN_SECRET_KEY` is missing or contains placeholder values, `/api/admin/status` reports `is_configured: false`, and all mutating routes immediately return `403 Forbidden ("Write operations disabled: Admin authentication is not configured")`.

