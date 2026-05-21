---
name: testing-raffle-app
description: Test the raffle/exam web app end-to-end. Use when verifying registration, admin panel, or ticket flows.
---

# Testing the Raffle App

## Architecture
- **Backend**: FastAPI app in `backend/main.py`, uses JSON file storage at `/data/`
- **Frontend**: Static `index.html` served via GitHub Pages (domain: miranda.wiki)
- **Admin panel**: Static `admin.html` also on GitHub Pages
- **Production API**: Hosted on Railway at `https://my-production-c42f.up.railway.app`

## Local Testing Setup

1. Create data directory and start backend:
   ```bash
   sudo mkdir -p /data && sudo chmod 777 /data
   cd /home/ubuntu/repos/my/backend
   pip install fastapi uvicorn
   uvicorn main:app --host 0.0.0.0 --port 8001 &
   ```

2. Create local HTML copies pointing to localhost:
   ```bash
   cd /home/ubuntu/repos/my
   sed 's|https://my-production-c42f.up.railway.app|http://localhost:8001|g' index.html > /tmp/test-index.html
   sed 's|https://my-production-c42f.up.railway.app|http://localhost:8001|g' admin.html > /tmp/test-admin.html
   ```

3. Open `file:///tmp/test-index.html` and `file:///tmp/test-admin.html` in Chrome

## Key Flows

### Registration
- Home page → Click "Розыгрыш" → Click "Впервые" → Fill nickname + phone → Click "Зарегистрироваться"
- On success, shows access code (XXXX-XXXX-XXXX format)

### Admin Panel
- Open admin.html → Enter admin password → Click "Войти"
- Default admin password: stored in `ADMIN_PASSWORD` env var, falls back to `admin2024`
- Switch to "Пользователи" tab to see user list with phone numbers

### API Testing
```bash
# Health check
curl -s http://localhost:8001/health

# Register user
curl -s -X POST http://localhost:8001/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"nickname": "TestUser", "phone": "+79001234567"}'

# Get users (admin)
curl -s http://localhost:8001/api/users -H "Authorization: Bearer admin2024"
```

## Seeding Test Data
To simulate old users (e.g., registered before a feature was added):
```python
import json
users = [{'id': 'U-OLD', 'nickname': 'OldUser', 'access_code': 'AAAA-BBBB-CCCC', 'registered_at': '2026-01-01T00:00:00'}]
json.dump(users, open('/data/users.json', 'w'), ensure_ascii=False, indent=2)
```

## Known Issues
- Railway deployment might lag behind the GitHub repo. If production API behaves differently from local, check if Railway has the latest code deployed.
- Cyrillic text input via computer-use tool may not work directly in browser inputs. Use `browser_console` to set input values programmatically.
- The app uses file-based JSON storage (`/data/users.json`, `/data/tickets.json`). Clean these between test runs for isolation.

## Devin Secrets Needed
- No secrets required for local testing (default admin password is `admin2024`)
- For production testing, the `ADMIN_PASSWORD` environment variable on Railway may differ from the default
