# CyberCase Intelligence Framework - FastAPI Backend

This is the Python-based backend for the CyberCase Intelligence Framework RAG platform.

## Tech Stack
- **FastAPI**: Web framework.
- **SQLAlchemy**: ORM.
- **Alembic**: Database migrations.
- **Pydantic**: Data validation and settings.
- **Asyncpg**: Async PostgreSQL driver.

## Getting Started

### 1. Setup Environment
Ensure you have the virtual environment activated from the root directory.

```bash
# From project root
.\env_mitre\Scripts\activate
```

### 2. Configuration
Create a `.env` file in this directory based on the defaults in `app/config.py`.

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cybercase
CORS_ORIGINS=http://localhost:3000
DEBUG=True
ANTHROPIC_API_KEY=your_key_here
RAG_SERVICE_URL=http://localhost:8001
```

### 3. Database Migrations
Run the migrations to set up the database schema.

```bash
alembic upgrade head
```

### 4. Run the Server
Start the FastAPI server with hot-reload.

```bash
uvicorn app.main:app --reload
```

The API documentation will be available at `http://localhost:8000/docs`.
