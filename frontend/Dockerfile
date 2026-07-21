FROM node:22-alpine

# Next.js telemetry and sharp can sometimes require libc6-compat on alpine
RUN apk add --no-cache libc6-compat

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@10 --activate

WORKDIR /app

# Copy all package configuration files, including the workspace file!
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./

# Install dependencies
RUN pnpm install

# We don't copy the source code here because we will mount it 
# as a volume in docker-compose.yml for hot-reloading during dev.
# For production, you would COPY . . and run pnpm build.

CMD ["pnpm", "dev"]
