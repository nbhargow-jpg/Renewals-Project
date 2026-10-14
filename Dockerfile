# ==========================================
# Stage 1: Build the React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Production Python Backend & Web App
# ==========================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install curl for healthchecks and utility dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend, migrations, assets, and scripts
COPY backend /app/backend
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY assets /app/assets
COPY data /app/data
COPY scripts /app/scripts

# Copy compiled frontend from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Setup runtime directories, strip Windows CRLF line endings, and ensure executable permissions
RUN mkdir -p /app/uploads /app/data /app/scratch && \
    sed -i 's/\r$//' /app/scripts/entrypoint.sh && \
    chmod +x /app/scripts/entrypoint.sh

# Dynamic Railway port (defaults to 8000 if not set)
ENV PORT=8000
EXPOSE 8000

# Run entrypoint script
CMD ["/app/scripts/entrypoint.sh"]
