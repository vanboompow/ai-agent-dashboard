# Multi-stage build for optimized production image
FROM node:18-alpine AS base

# Set working directory
WORKDIR /app

# Install basic dependencies
RUN apk add --no-cache \
    curl \
    && rm -rf /var/cache/apk/*

# Development stage
FROM base AS development

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev dependencies)
RUN npm ci

# Copy source code
COPY . .

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 -G nodejs
RUN chown -R nextjs:nodejs /app
USER nextjs

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5173 || exit 1

# Expose port
EXPOSE 5173

# Development command
CMD ["npm", "run", "dev", "--", "--host"]

# Build stage
FROM base AS builder

# Copy package files
COPY package*.json ./

# Install dependencies (including dev dependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Build arguments for metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Add metadata labels
LABEL org.opencontainers.image.title="AI Agent Dashboard Frontend" \
      org.opencontainers.image.description="React frontend for AI Agent Dashboard" \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.source="https://github.com/your-org/ai-agent-dashboard" \
      org.opencontainers.image.licenses="MIT"

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built application from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create non-root user for Nginx
RUN addgroup -g 1001 -S nginx && \
    adduser -S nginx -u 1001 -G nginx

# Set proper permissions
RUN chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    chown -R nginx:nginx /usr/share/nginx/html && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Switch to non-root user
USER nginx

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80 || exit 1

# Expose port
EXPOSE 80

# Production command
CMD ["nginx", "-g", "daemon off;"]

# Testing stage
FROM builder AS testing

# Install additional test dependencies
RUN npm install -g @playwright/test

# Copy test files
COPY e2e/ ./e2e/
COPY src/__tests__/ ./src/__tests__/

# Run tests
RUN npm run test:coverage
RUN npm run lint
RUN npm run type-check

# Default to production stage
FROM production AS final