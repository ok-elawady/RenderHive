# Stage 1: Builder
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project configuration files
COPY pyproject.toml uv.lock ./

ARG DEV=false

# Install dependencies using cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$DEV" = "true" ]; then \
        uv sync --frozen --no-install-project; \
    else \
        uv sync --frozen --no-install-project --no-dev; \
    fi

# Stage 2: Runner
FROM python:3.13-slim AS runner

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Place virtual environment on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source code
COPY . .

# Copy entrypoint to a location outside the volume mount to prevent Windows host from shadowing it with a CRLF version
RUN cp entrypoint.sh /usr/local/bin/entrypoint.sh && \
    sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
