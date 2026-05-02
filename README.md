# TrustMedia

**Unified Digital Media Trust Platform Using Multimodal Deepfake Detection and Blockchain Provenance**

Given a video input, returns:
- **Authentic** - Media verified as genuine
- **Suspicious** - Potential manipulation detected
- **Manipulated** - High confidence of tampering

## First-time setup

The API refuses to boot without a populated `.env` (`DATABASE_URL` and `JWT_SECRET` are required, and `JWT_SECRET` is validated for length and weak values).

```bash
cd services/api
cp .env.example .env

# Generate a strong JWT secret and append it to .env
python3 -c "import secrets; print(f'JWT_SECRET={secrets.token_urlsafe(32)}')" >> .env

# Edit .env and replace CHANGE_ME in DATABASE_URL with a real password.
# Then create the schema:
alembic upgrade head
```

## Quick Start

```bash
# 1. Backend (after first-time setup above)
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Worker (new terminal)
cd services/api && source .venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info -Q analysis,blockchain

# 3. Frontend (new terminal)
cd apps/web
npm install && cp .env.example .env.local
npm run dev

# 4. Smart Contract (optional)
cd contracts && npm install
npx hardhat node  # separate terminal
npm run deploy:local
```

Open http://localhost:3000

## Project Structure

```
apps/web/          Next.js frontend (TypeScript, Tailwind, shadcn/ui)
services/api/      FastAPI backend (Python, SQLAlchemy, Celery)
services/worker/   Celery worker entrypoint
contracts/         Solidity smart contract (Hardhat)
docker/            Dockerfiles
docs/              Architecture, API spec, setup guides
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Local Setup](docs/SETUP.md)
- [Deployment](docs/DEPLOYMENT.md)

## Requirements

- Python 3.11+, Node.js 20+
- PostgreSQL 16, Redis 7, FFmpeg

## License

MIT
