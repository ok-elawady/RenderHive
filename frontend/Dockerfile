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

# Copy source code into the image.
# On local dev, docker-compose.override.yml mounts the host source over /app,
# so this baked copy is shadowed and hot-reload works as normal.
# On cloud deployments (no volume mount), this baked copy is used directly.
COPY . .

CMD ["pnpm", "dev"]
