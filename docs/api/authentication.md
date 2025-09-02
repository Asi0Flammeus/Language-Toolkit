# Authentication Guide

## Overview

The Language Toolkit API uses JWT (JSON Web Token) based authentication. Clients authenticate using OAuth2 client credentials flow to obtain access tokens.

## Configuration

### Setting Up Client Credentials

Client credentials are now configured through environment variables in the `.env` file:

#### Single Client Setup

For a single client application, add these to your `.env`:

```env
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_secure_secret_here
```

#### Multiple Clients Setup

For multiple client applications, use numbered environment variables:

```env
# First client
CLIENT_ID_1=web_app_client
CLIENT_SECRET_1=web_app_secret_key_here

# Second client
CLIENT_ID_2=mobile_app_client
CLIENT_SECRET_2=mobile_app_secret_key_here

# Third client
CLIENT_ID_3=service_client
CLIENT_SECRET_3=service_secret_key_here
```

### Security Configuration

Configure JWT settings in `.env`:

```env
# JWT Secret Key (IMPORTANT: Change in production!)
SECRET_KEY=your-secret-jwt-signing-key-here

# Token expiration in minutes (default: 60)
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## Authentication Flow

### 1. Obtain Access Token

Request a JWT token using your client credentials:

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_client_id&password=your_client_secret&grant_type=password"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 2. Use Access Token

Include the token in the Authorization header for API requests:

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  "http://localhost:8000/translate/pptx"
```

## Code Examples

### Python

```python
import requests

# Configuration
API_BASE = "http://localhost:8000"
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# Get access token
token_response = requests.post(
    f"{API_BASE}/token",
    data={
        "username": CLIENT_ID,
        "password": CLIENT_SECRET,
        "grant_type": "password"
    }
)

token = token_response.json()["access_token"]

# Use token for API requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{API_BASE}/tasks", headers=headers)
```

### JavaScript

```javascript
const API_BASE = 'http://localhost:8000';
const CLIENT_ID = 'your_client_id';
const CLIENT_SECRET = 'your_client_secret';

// Get access token
async function getToken() {
  const response = await fetch(`${API_BASE}/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      username: CLIENT_ID,
      password: CLIENT_SECRET,
      grant_type: 'password'
    })
  });
  
  const data = await response.json();
  return data.access_token;
}

// Use token for API requests
async function makeAPIRequest(token) {
  const response = await fetch(`${API_BASE}/tasks`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  return response.json();
}
```

## Testing Authentication

Run the authentication test script:

```bash
# Make sure your .env file has CLIENT_ID and CLIENT_SECRET configured
python tests/test_auth.py
```

## Security Best Practices

1. **Never commit credentials**: Keep your `.env` file out of version control
2. **Use strong secrets**: Generate secure random strings for CLIENT_SECRET
3. **Rotate credentials**: Regularly update client secrets
4. **Use HTTPS in production**: Always use SSL/TLS in production environments
5. **Short token expiration**: Keep ACCESS_TOKEN_EXPIRE_MINUTES reasonably short
6. **Secure JWT secret**: Use a strong, unique SECRET_KEY for JWT signing

## Migration from Old Authentication

The API uses OAuth2 client credentials flow exclusively. All authentication is configured via environment variables in the `.env` file as shown above. 

To test authentication:
```bash
python tests/test_auth.py
```

## Troubleshooting

### No credentials found
If you see "No client credentials found in environment variables":
- Check that your `.env` file exists and contains CLIENT_ID and CLIENT_SECRET
- Ensure the API server is reading from the correct `.env` file location
- Restart the API server after updating `.env`

### Invalid credentials
If authentication fails with 401 Unauthorized:
- Verify CLIENT_ID and CLIENT_SECRET match exactly in `.env`
- Check for trailing spaces or special characters
- Ensure you're using the correct grant_type: "password"

### Token expired
If you get 401 after successful authentication:
- Your token may have expired (default: 60 minutes)
- Request a new token using the /token endpoint
- Consider implementing token refresh in your client application