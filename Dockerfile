# Multi-stage build for ProPublica MCP Server
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set labels for metadata
LABEL org.opencontainers.image.title="ProPublica MCP Server" \
      org.opencontainers.image.description="MCP server providing access to ProPublica Nonprofit Explorer API for Form 990 data, financial analysis, and nonprofit research. Includes tools for searching organizations, analyzing financials, and exporting data for CRM integration." \
      org.opencontainers.image.version=${VERSION} \
      org.opencontainers.image.created=${BUILD_DATE} \
      org.opencontainers.image.revision=${VCS_REF} \
      org.opencontainers.image.vendor="ProPublica MCP" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/asachs01/propublica-mcp"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# Create non-root user
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage and fix ownership
COPY --from=builder /opt/venv /opt/venv
RUN chown -R mcpuser:mcpuser /opt/venv

# Create app directory and set ownership
RUN mkdir -p /app && chown mcpuser:mcpuser /app
WORKDIR /app

# Copy application code
COPY --chown=mcpuser:mcpuser src/ ./src/
COPY --chown=mcpuser:mcpuser pyproject.toml ./
COPY --chown=mcpuser:mcpuser README.md ./

# Switch to non-root user and install the package
USER mcpuser
RUN pip install .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('https://projects.propublica.org/nonprofits/api/v2/search.json?q=test', timeout=5)" || exit 1

# Expose port (MCP typically uses stdin/stdout, but useful for potential HTTP interface)
EXPOSE 8000

# Set default command
CMD ["python", "-m", "propublica_mcp.server"] 