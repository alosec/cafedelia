# Dockerfile for Cafedelia - TypeScript backend containerization
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY cafed/package*.json ./
COPY cafed/tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy TypeScript source
COPY cafed/ ./

# Build TypeScript to JavaScript
RUN npm run build

# Production stage
FROM node:18-alpine AS production

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S cafed -u 1001

# Set working directory
WORKDIR /app

# Copy built application
COPY --from=builder --chown=cafed:nodejs /app/dist ./dist
COPY --from=builder --chown=cafed:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=cafed:nodejs /app/package*.json ./

# Switch to non-root user
USER cafed

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:8001/health', (res) => { process.exit(res.statusCode === 200 ? 0 : 1) })"

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["node", "dist/index.js"]