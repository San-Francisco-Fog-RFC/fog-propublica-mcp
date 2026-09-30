# Deployment Guide

This guide covers deploying the ProPublica MCP Server to various cloud platforms.

## 🚀 One-Click Deployments

### DigitalOcean App Platform

[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/asachs01/propublica-mcp/tree/main)

**Features:**
- Container-based deployment using Dockerfile
- Automatic scaling and load balancing
- Built-in monitoring and alerting
- Custom domain support
- Environment variable management

**Configuration:**
The deployment uses the `.do/deploy.template.yaml` file which configures:
- Container settings (basic-xxs instance)
- Environment variables (LOG_LEVEL, API_RATE_LIMIT, etc.)
- Health checks and alerts
- Auto-deployment from GitHub

**Cost:** Starting at $5/month for basic-xxs instance

### Cloudflare Workers

[![Deploy to Cloudflare Workers](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/asachs01/propublica-mcp)

**Features:**
- Serverless deployment with global edge distribution
- Zero cold starts
- Automatic scaling to zero
- Built-in DDoS protection
- Custom domain support

**Configuration:**
The deployment uses `wrangler.toml` and `package.json` to configure:
- Worker settings and compatibility flags
- Environment variables for different environments
- Build and deployment scripts

**Cost:** Free tier with 100,000 requests/day, paid plans start at $5/month

## Manual Deployment Instructions

### DigitalOcean App Platform (Manual)

1. **Prerequisites:**
   - DigitalOcean account
   - GitHub repository (public or with proper access)

2. **Setup:**
   ```bash
   # Fork or clone the repository
   git clone https://github.com/asachs01/propublica-mcp.git
   cd propublica-mcp
   
   # Push to your own repository
   git remote set-url origin https://github.com/YOUR_USERNAME/propublica-mcp.git
   git push origin main
   ```

3. **Deploy:**
   - Go to DigitalOcean Apps dashboard
   - Click "Create App"
   - Connect your GitHub repository
   - Select the repository and branch
   - DigitalOcean will auto-detect the `.do/deploy.template.yaml`
   - Review and modify environment variables if needed
   - Click "Deploy"

4. **Post-deployment:**
   - Your app will be available at: `https://your-app-name.ondigitalocean.app`
   - Configure custom domain if desired
   - Set up monitoring and alerts

### Cloudflare Workers (Manual)

1. **Prerequisites:**
   - Cloudflare account
   - Node.js 18+ and npm installed locally
   - Wrangler CLI

2. **Setup:**
   ```bash
   # Install Wrangler globally
   npm install -g wrangler
   
   # Clone repository
   git clone https://github.com/asachs01/propublica-mcp.git
   cd propublica-mcp
   
   # Install dependencies
   npm install
   
   # Login to Cloudflare
   wrangler login
   ```

3. **Deploy:**
   ```bash
   # Deploy to production
   npm run deploy
   
   # Or deploy to staging
   wrangler deploy --env staging
   ```

4. **Post-deployment:**
   - Your worker will be available at: `https://propublica-mcp.YOUR_SUBDOMAIN.workers.dev`
   - Configure custom domain if desired
   - Set up monitoring in Cloudflare dashboard

## Environment Variables

Both platforms support the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `API_RATE_LIMIT` | Requests per minute to ProPublica API | 60 |
| `PROPUBLICA_API_BASE_URL` | Base URL for ProPublica API | https://projects.propublica.org/nonprofits/api/v2 |

## Custom Domain Configuration

### DigitalOcean
1. Go to your app settings
2. Click "Domains"
3. Add your custom domain
4. Update DNS records as instructed

### Cloudflare
1. Go to Workers dashboard
2. Select your worker
3. Click "Custom Domains"
4. Add your domain (must be on Cloudflare)

## Monitoring and Logging

### DigitalOcean
- Built-in application metrics
- Log streaming and retention
- Email/Slack alerts for deployments and errors
- Health check endpoints

### Cloudflare
- Real-time analytics in dashboard
- Request logs and error tracking
- Performance metrics
- Custom alerting via webhooks

## Scaling

### DigitalOcean
- Manual scaling: Change instance size or count
- Auto-scaling: Configure based on CPU/memory usage
- Load balancer automatically distributes traffic

### Cloudflare
- Automatic scaling to handle any load
- Global edge distribution
- No manual intervention required

## Troubleshooting

### Common Issues

1. **Deployment Failed:**
   - Check repository permissions
   - Verify configuration files are properly formatted
   - Review build logs for errors

2. **Environment Variables Not Working:**
   - Ensure variables are set in platform configuration
   - Check variable names match exactly
   - Restart service after changes

3. **Custom Domain Issues:**
   - Verify DNS records are correct
   - Allow time for propagation (up to 24 hours)
   - Check SSL certificate status

### Getting Help

- **DigitalOcean:** [Support documentation](https://docs.digitalocean.com/products/app-platform/)
- **Cloudflare:** [Workers documentation](https://developers.cloudflare.com/workers/)
- **ProPublica MCP:** [GitHub Issues](https://github.com/asachs01/propublica-mcp/issues)

## Security Considerations

- Keep environment variables secure (no secrets in public repos)
- Use HTTPS endpoints only
- Regularly update dependencies
- Monitor access logs for unusual activity
- Set appropriate rate limits

## Cost Optimization

### DigitalOcean
- Start with basic-xxs instance ($5/month)
- Scale up only when needed
- Use auto-scaling to optimize costs
- Monitor usage to avoid unexpected charges

### Cloudflare
- Free tier covers most development/testing
- Monitor request counts to stay within limits
- Paid plans offer better performance and features
- No data egress charges 