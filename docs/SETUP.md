# TrustMedia - Local Development Setup

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Redis 7
- FFmpeg
- Git

### Install system dependencies (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
  postgresql postgresql-contrib redis-server ffmpeg
```

### Install system dependencies (macOS)
```bash
brew install python@3.11 postgresql@16 redis ffmpeg node
brew services start postgresql@16
brew services start redis
```

## Step 1: Clone and prepare
```bash
cd finalyear
```

## Step 2: Set up PostgreSQL
```bash
sudo -u postgres psql -c "CREATE DATABASE deepfake_trust;"
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE deepfake_trust TO postgres;"
```

## Step 3: Backend API
```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local)

# Start API server
uvicorn app.main:app --reload --port 8000
```

## Step 4: Celery Worker (separate terminal)
```bash
cd services/api
source .venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info -Q analysis,blockchain
```

## Step 5: Smart Contract (optional)
```bash
cd contracts
npm install

# Local hardhat node (separate terminal)
npx hardhat node

# Deploy to local
npm run deploy:local

# Copy the printed CONTRACT_ADDRESS to your .env files
```

### Deploy to Polygon Amoy testnet
```bash
# Get test MATIC from https://faucet.polygon.technology/
# Set PRIVATE_KEY in contracts/.env
cp .env.example .env
npm run deploy:amoy
```

## Step 6: Frontend
```bash
cd apps/web
npm install
cp .env.example .env.local
# Edit .env.local with your contract address if deployed

npm run dev
```

## Step 7: Verify everything works
1. Open http://localhost:3000 (frontend)
2. Open http://localhost:8000/docs (API docs)
3. Upload a test video
4. Watch the analysis progress
5. View results

## Using Docker (Alternative)
```bash
# From project root
cp services/api/.env.example services/api/.env
docker-compose up --build
```

## Demo Mode
By default, `DEMO_MODE=true` in the API config. This:
- Limits frame extraction to 30 frames
- Runs inference on CPU
- Works without GPU

To run with full analysis, set `DEMO_MODE=false` and `MODEL_DEVICE=cuda` (requires NVIDIA GPU).

## Running Tests
```bash
# API tests
cd services/api
source .venv/bin/activate
pytest tests/ -v

# Contract tests
cd contracts
npm test
```
