# API Keys Migration Guide

## Important: API Keys Configuration Change

As of the latest update, all API keys should be configured in the `.env` file. The `api_keys.json` file is now deprecated.

## Migration Steps

### 1. Check Your Current Configuration

If you have an existing `api_keys.json` file with your API keys:

```bash
cat api_keys.json
```

### 2. Copy Keys to .env File

Add all your API keys to the `.env` file:

```bash
# Edit .env file
nano .env
```

Make sure your `.env` file contains:

```env
# API Keys (Required)
DEEPL_API_KEY=your_actual_deepl_key_here
OPENAI_API_KEY=your_actual_openai_key_here
ELEVENLABS_API_KEY=your_actual_elevenlabs_key_here
CONVERTAPI_SECRET=your_actual_convertapi_secret_here

# Optional: AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Remove Old Configuration (Optional)

Once you've confirmed that all keys are in `.env` and the API server is working:

```bash
# Backup first (optional)
mv api_keys.json api_keys.json.backup

# Or remove entirely
rm api_keys.json
```

### 4. Verify Configuration

Start the API server and check that it loads keys from `.env`:

```bash
source env/bin/activate
python api_server.py
```

You should see in the logs that API keys are being loaded from environment variables.

## Benefits of Using .env

1. **Standard Practice**: Using `.env` for configuration is a widely adopted best practice
2. **Security**: Environment variables are more secure than JSON files
3. **Flexibility**: Easier to override values in different environments
4. **Simplicity**: Single source of truth for all configuration

## Troubleshooting

If the API server can't find your keys:

1. Ensure `.env` file exists in the project root
2. Check that all key names are exactly as shown above
3. Restart the API server after making changes
4. Check server logs for specific error messages

## Note for Docker Users

If you're using Docker, make sure to update your `docker-compose.yml` or Docker run commands to properly pass the environment variables from `.env` file.