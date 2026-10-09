# syntax=docker/dockerfile:1
# --- Build Stage ---
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency definitions
COPY package*.json ./
RUN npm ci

# Copy application source code
COPY . .

# Build production assets
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Remove default nginx site
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom reverse proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built artifacts from builder
COPY --from=build /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
