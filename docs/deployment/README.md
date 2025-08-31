# Deployment Documentation

This section covers various deployment options for the Language Toolkit.

## Deployment Options

### [Local Deployment](local.md)
Best for development and testing:
- Quick setup with minimal configuration
- Direct access to logs and debugging
- Ideal for single-user scenarios

### [Production Deployment](production.md)
For production environments:
- System service configuration
- Security best practices
- Performance optimization
- Monitoring and logging

### [Docker Deployment](docker.md)
Container-based deployment:
- Consistent environment across platforms
- Easy scaling and orchestration
- Simplified dependency management
- Docker Compose for multi-service setup

## Quick Decision Guide

Choose your deployment method based on your needs:

| Scenario | Recommended Method | Guide |
|----------|-------------------|-------|
| Development/Testing | Local | [local.md](local.md) |
| Single Server Production | SystemD Service | [production.md](production.md) |
| Containerized Environment | Docker | [docker.md](docker.md) |
| Microservices Architecture | Docker Compose | [docker.md](docker.md#docker-compose) |

## Common Configuration

All deployment methods require:

1. **API Keys Configuration** (`.env` file):
```bash
# Copy from .env.example
cp .env.example .env

# Then configure your API keys:
DEEPL_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key
ELEVENLABS_API_KEY=your-api-key
CONVERTAPI_SECRET=your-api-key
ANTHROPIC_API_KEY=your-api-key
```

2. **Language Configuration** (`supported_languages.json`)
3. **Authentication Tokens** (`auth_tokens.json` for API)

## Environment Variables

Common environment variables across deployments:

```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
MAX_WORKERS=4

# File Limits
MAX_PPTX_SIZE=52428800  # 50MB
MAX_TEXT_SIZE=10485760  # 10MB
MAX_AUDIO_SIZE=209715200  # 200MB

# Paths
UPLOAD_DIR=/tmp/uploads
OUTPUT_DIR=/tmp/outputs
```

## Security Considerations

1. **API Keys**: Never commit `.env` file to version control (use `.env.example` as template)
2. **Authentication**: Always use strong authentication tokens
3. **HTTPS**: Use reverse proxy with SSL in production
4. **File Validation**: Configure appropriate file size limits
5. **Network**: Restrict access to trusted networks

## Monitoring

Recommended monitoring setup:
- Application logs: `/var/log/language-toolkit/`
- System metrics: CPU, memory, disk usage
- API metrics: Request rate, response time, error rate
- Health checks: Regular endpoint monitoring

## Troubleshooting

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| Port already in use | Change port in configuration |
| Permission denied | Check file permissions and user rights |
| API key errors | Verify API keys in configuration |
| Memory issues | Increase system resources or adjust worker count |

For detailed troubleshooting, see the specific deployment guide for your chosen method.