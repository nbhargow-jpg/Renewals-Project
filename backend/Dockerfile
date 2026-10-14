FROM python:3.12-slim

# Prevent python from buffering stdout/stderr and writing pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies (curl for healthcheck, libpq dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source code and migrations
COPY backend /app/backend
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY assets /app/assets

# Create uploads and data directories with appropriate permissions
RUN mkdir -p /app/uploads /app/data /app/scratch

EXPOSE 8000

# Run alembic upgrade head followed by uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
