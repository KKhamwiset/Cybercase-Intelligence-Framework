# TSR Mitre Backend (ElysiaJS)

This is the high-performance backend for the TSR Mitre RAG platform, built with [ElysiaJS](https://elysiajs.com/) and running on the [Bun](https://bun.sh/) runtime.

## Tech Stack
- **Runtime**: Bun
- **Framework**: ElysiaJS
- **ORM**: Prisma
- **Database**: PostgreSQL
- **Validation**: TypeBox

## Getting Started

1. **Install Dependencies**:
   ```bash
   bun install
   ```

2. **Generate Prisma Client**:
   ```bash
   npx prisma generate
   ```

3. **Configure Environment**:
   Ensure you have a `.env` file with your `DATABASE_URL`.

4. **Development**:
   To start the development server with hot-reload:
   ```bash
   bun run dev
   ```

## API Documentation
The API is available at `http://localhost:8000`. 
- Health Check: `GET /api/v1/health`
- Users API: `GET /api/v1/users`, `POST /api/v1/users`