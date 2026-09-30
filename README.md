# ProPublica MCP Server

A Model Context Protocol (MCP) server that provides access to ProPublica's Nonprofit Explorer API, enabling AI models to search and analyze nonprofit organizations' Form 990 data for CRM integration and prospect research.

## Features

- Search nonprofit organizations by name, location, and category
- Retrieve detailed organization profiles and contact information
- Access Form 990 financial data and filing history
- Analyze financial trends across multiple years
- Export data in CRM-ready formats
- Built with FastMCP for optimal performance

## 🚀 One-Click Deployment

Deploy the ProPublica MCP server instantly to your preferred cloud platform:

### DigitalOcean App Platform
[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/asachs01/propublica-mcp/tree/main)

### Cloudflare Workers
[![Deploy to Cloudflare Workers](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/asachs01/propublica-mcp)

Both platforms offer:
- **DigitalOcean**: Container-based deployment with automatic scaling and monitoring
- **Cloudflare**: Serverless deployment with global edge distribution and zero cold starts

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Git

### Installation

#### Option 1: Docker (Recommended)

The easiest way to run the ProPublica MCP server is using Docker:

**Quick Start with Docker:**
```bash
# Pull the latest image from GitHub Container Registry
docker pull ghcr.io/asachs/propublica-mcp:latest

# Run the server
docker run -it --rm ghcr.io/asachs/propublica-mcp:latest
```

**Using Docker Compose:**
1. Download the compose file:
```bash
curl -O https://raw.githubusercontent.com/asachs/propublica-mcp/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/asachs/propublica-mcp/main/env.example
```

2. Configure environment (optional):
```bash
cp env.example .env
# Edit .env file with your preferred settings
```

3. Start the service:
```bash
docker-compose up -d
```

#### Option 2: Cloud Deployment

**DigitalOcean App Platform:**
1. Click the "Deploy to DO" button above
2. Connect your GitHub account (if not already connected)
3. Configure environment variables (optional - defaults are provided)
4. Click "Deploy" - your app will be live in minutes with a public URL

**Cloudflare Workers:**
1. Click the "Deploy to Cloudflare Workers" button above
2. Connect your GitHub account and authorize Cloudflare
3. Configure any environment variables as needed
4. Deploy - your serverless function will be live globally

#### Option 3: Local Python Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd propublica-mcp
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package:
```bash
pip install -e .
```

5. Run the server:
```bash
python -m propublica_mcp.server
```

### Usage with Claude Desktop

#### For Cloud Deployment:
**DigitalOcean/Cloudflare (HTTP endpoint):**
```json
{
  "mcpServers": {
    "propublica-mcp": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "https://your-deployed-url.com/mcp"
      ],
      "description": "ProPublica Nonprofit Explorer MCP Server (Cloud)"
    }
  }
}
```

#### For Docker Deployment:
```json
{
  "mcpServers": {
    "propublica-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "ghcr.io/asachs/propublica-mcp:latest"
      ],
      "description": "ProPublica Nonprofit Explorer MCP Server"
    }
  }
}
```

#### For Local Installation:
```json
{
  "mcpServers": {
    "propublica-mcp": {
      "command": "python",
      "args": ["-m", "propublica_mcp.server"],
      "cwd": "/path/to/propublica-mcp",
      "env": {}
    }
  }
}
```

## API Tools

### Core Tools

- **search_nonprofits**: Search for nonprofit organizations
- **get_organization**: Get detailed organization information by EIN
- **get_organization_filings**: Retrieve Form 990 filings for an organization

### Advanced Tools

- **analyze_nonprofit_financials**: Analyze financial trends across multiple years
- **search_similar_nonprofits**: Find similar organizations
- **export_nonprofit_data**: Format data for CRM import

## Data Sources

This server uses the [ProPublica Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api) which provides:

- IRS Form 990 data for tax-exempt organizations
- Organization profiles and contact information
- Financial data and filing history
- NTEE categorization and 501(c) status

## Development

### Project Structure

```
propublica-mcp/
├── src/
│   └── propublica_mcp/
│       ├── __init__.py
│       ├── server.py
│       ├── api_client.py
│       ├── models.py
│       └── tools/
├── tests/
├── config/
├── .github/
│   └── workflows/
├── Dockerfile
├── docker-compose.yml
├── env.example
├── requirements.txt
└── README.md
```

### Development with Docker

#### Building the Docker Image

```bash
# Build the image
docker build -t propublica-mcp:dev .

# Or use docker-compose
docker-compose build
```

#### Running Development Environment

```bash
# Run with docker-compose (includes volume mounts for development)
docker-compose -f docker-compose.yml -f docker-compose.override.yml up

# Run tests in container
docker run --rm -v $(pwd):/app propublica-mcp:dev pytest tests/ -v
```

#### Environment Variables

The Docker container supports these environment variables:

- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `API_RATE_LIMIT`: Requests per minute (default: 60)
- `PROPUBLICA_API_BASE_URL`: API base URL (rarely needs changing)

### Running Tests

#### Local Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src/propublica_mcp
```

#### Docker Testing

```bash
# Run tests in Docker
docker run --rm ghcr.io/asachs/propublica-mcp:latest \
  python -m pytest tests/ -v

# Or with docker compose
docker compose run --rm propublica-mcp pytest tests/ -v
```

### Publishing to GitHub Container Registry

The project includes automated publishing via GitHub Actions, but you can also publish manually:

#### Prerequisites

1. **GitHub Personal Access Token** with `packages:write` scope
2. **Authentication to GitHub Container Registry**:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
   ```

#### Automated Publishing (Recommended)

Push to the `main` branch or create a tag to trigger automated builds:

```bash
# Trigger build for main branch
git push origin main

# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0
```

#### Manual Publishing

Use the provided script (requires local setup):

```bash
# Build and publish latest
./scripts/docker-publish.sh

# Build and publish specific version
./scripts/docker-publish.sh v1.0.0
```

#### Available Images

Once published, the images will be available at:

- **Latest**: `ghcr.io/asachs/propublica-mcp:latest`
- **Tagged versions**: `ghcr.io/asachs/propublica-mcp:v1.0.0`
- **Branch builds**: `ghcr.io/asachs/propublica-mcp:main`

### Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check the documentation
- Review existing GitHub issues
- Create a new issue with detailed information 