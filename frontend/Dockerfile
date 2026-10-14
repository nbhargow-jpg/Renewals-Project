# --- Build Stage ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Copy built static bundle
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx reverse proxy configuration
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
