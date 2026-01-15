# Vaultwarden Proxy

A lightweight HTTP API proxy for Vaultwarden that exposes user and vault statistics in a format compatible with Homepage dashboard widgets.

## Features

- Health check endpoint
- Statistics endpoint returning user counts and vault item counts
- Admin token authentication
- Configurable cache timeout (default: 5 minutes)
- Lightweight Flask-based API
- Docker container ready

## Environment Variables

- `VAULTWARDEN_URL` - Base URL for Vaultwarden (default: `http://vaultwarden:80`)
- `ADMIN_TOKEN` - Vaultwarden admin token for authentication (required)
- `CACHE_TIMEOUT` - Cache duration in seconds (default: `300` / 5 minutes)

## Getting Your Admin Token

To get your Vaultwarden admin token:

1. Go to your Vaultwarden admin panel: `https://your-vaultwarden-url/admin`
2. Log in with your admin password
3. The admin token is stored in your browser's cookies or can be found in your Vaultwarden configuration
4. Alternatively, check your Vaultwarden `.env` file for `ADMIN_TOKEN`

## Endpoints

### GET /health
Returns `OK` with status 200 if the service is running.

### GET /stats
Returns Vaultwarden user statistics in JSON format:

```json
{
    "total_users": 5,
    "active_users": 3
}
```

Where:
- `total_users`: Total number of registered users
- `active_users`: Number of users active in the last 30 days (based on last login time)

**Note:** The Vaultwarden admin API does not expose vault item counts (passwords, notes, etc.) through admin endpoints. Only user statistics are available for privacy/security reasons.

## Docker Usage

```bash
docker run -d \
  --name vaultwarden-proxy \
  -p 8428:5000 \
  -e VAULTWARDEN_URL=http://vaultwarden:80 \
  -e ADMIN_TOKEN=your_admin_token_here \
  -e CACHE_TIMEOUT=300 \
  ghcr.io/lioncitygaming/vaultwarden-proxy:latest
```

## Docker Compose

```yaml
services:
  vaultwarden-proxy:
    image: ghcr.io/lioncitygaming/vaultwarden-proxy:latest
    container_name: vaultwarden-proxy
    ports:
      - "8428:5000"
    environment:
      - VAULTWARDEN_URL=http://vaultwarden:80
      - ADMIN_TOKEN=your_admin_token_here
      - CACHE_TIMEOUT=300
    restart: unless-stopped
```

## Homepage Widget Configuration

Add this to your Homepage `services.yaml`:

```yaml
- Vaultwarden:
    icon: vaultwarden.png
    href: https://your-vaultwarden-url
    description: Password Manager
    widget:
        type: customapi
        url: http://your-server:5152/stats
        refreshInterval: 300000  # 5 minutes
        mappings:
            - field: total_users
              label: Users
              format: number
            - field: active_users
              label: Active (30d)
              format: number
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export VAULTWARDEN_URL=http://localhost:80
export ADMIN_TOKEN=your_admin_token_here
python app.py
```

## Security Notes

- The admin token provides full administrative access to your Vaultwarden instance
- Keep the token secure and never commit it to version control
- Use environment variables or secrets management for the token
- Consider running this proxy on an internal network only

## Known Limitations

- **Vault item counts not available**: The Vaultwarden admin API does not expose vault item counts (passwords, notes, cards, identities) for privacy/security reasons. Only user statistics are available.
- Active user detection relies on the `lastActive` field from the admin API
- Statistics are cached for the configured timeout period (default: 5 minutes)

## License

MIT
