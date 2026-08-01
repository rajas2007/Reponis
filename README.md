# Reponis

## Description
Reponis is an engineering intelligence platform designed for GitHub repositories. It analyzes repository activity, computes trustworthy engineering metrics (cycle time, code churn, issue metrics, etc.), stores those metrics, and generates AI summaries based ONLY on pre-computed metrics.

## Vision
To provide engineering teams with a clear, reliable, and actionable overview of their development processes through robust data analysis and AI-driven insights.

## Core Philosophy
1. **Analytics First:** Data and metrics are the foundation.
2. **AI Second:** AI serves only as an explanation layer based on pre-computed, trustworthy metrics.

## Tech Stack
- **Monorepo:** Turborepo, pnpm workspaces
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Recharts
- **Backend:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Celery, Redis
- **CI/CD:** GitHub Actions

## Repository Structure
```
reponis/
├── apps/
│   ├── api/     # FastAPI backend (Domain-driven modules)
│   └── web/     # Next.js frontend (Feature-first architecture)
├── docs/        # Minimal project documentation (Roadmap, Decisions)
├── .github/     # GitHub Actions CI workflows
```

## Getting Started

### Prerequisites
- Node.js >= 22
- pnpm >= 9
- Python >= 3.11
- PostgreSQL
- Redis

### Installation
1. Clone the repository
2. Run `pnpm install` in the root directory to install Node dependencies.
3. Set up the Python virtual environment and install backend dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ./apps/api[dev]
   ```
4. Copy `.env.example` to `.env` and configure your environment variables.

## Development Commands
From the monorepo root:
- `pnpm dev`: Run both frontend and backend development servers (requires turbo setup)
- `pnpm worker`: Start the Celery worker for background jobs
- `pnpm build`: Build the frontend and any necessary dependencies
- `pnpm lint`: Run linting across the monorepo
- `pnpm typecheck`: Run type checking across the monorepo

## Local Verification
Before pushing code, run the local verification system to ensure it matches the GitHub Actions CI pipeline:

**PowerShell (Windows):**
```powershell
./scripts/verify.ps1
```

**Bash (Linux/macOS):**
```bash
./scripts/verify.sh
```

## Project Architecture Overview
The project uses a startup-focused, feature-first architecture:
- **Domain-Driven Backend:** The FastAPI app is split into vertical feature modules (`auth`, `repositories`, `analytics`, etc.) rather than technical layers.
- **Feature-First Frontend:** The Next.js app groups logic into domain-specific features inside `src/features/` and uses `src/api/` for domain-grouped API clients.
- Every feature slice is independently scalable, maintaining clean architecture principles without unnecessary shared packages.

## Current Project Status
The repository is currently in the initial scaffolding phase with the foundation fully laid out and verified.
