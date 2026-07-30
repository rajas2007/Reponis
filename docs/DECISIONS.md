# Architectural Decisions

This document captures the major architectural decisions for Reponis as the project evolves through vertical slices.

### FastAPI as backend
- **Decision:** Use FastAPI for the backend API.
- **Reason:** Provides high performance, native async support, and excellent automatic OpenAPI documentation generation.
- **Expected benefit:** Rapid API development with strict type validation and fast execution.

### PostgreSQL as database
- **Decision:** Use PostgreSQL as the primary relational database.
- **Reason:** Robust, reliable, and supports advanced analytical queries and JSONB which is well-suited for storing Git metadata.
- **Expected benefit:** High data integrity and flexible querying capabilities.

### Celery + Redis for background processing
- **Decision:** Use Celery with Redis for background tasks.
- **Reason:** Asynchronous task processing is essential for heavy operations like repository synchronization without blocking the API.
- **Expected benefit:** Reliable task queuing and execution for long-running GitHub API interactions.

### Next.js for frontend
- **Decision:** Use Next.js (App Router) for the web application.
- **Reason:** Provides built-in optimizations, hybrid static/server rendering, and a robust routing system.
- **Expected benefit:** Excellent developer experience and highly performant frontend delivery.

### Feature-first architecture & Domain-driven backend
- **Decision:** Organize both frontend and backend codebases into vertical feature slices rather than horizontal technical layers.
- **Reason:** Keeps related code together, making it easier to understand, test, and modify specific business features independently.
- **Expected benefit:** Reduced context switching and more maintainable, scalable features as the project grows.

### Analytics-first philosophy
- **Decision:** Build the platform centered around computing trustworthy engineering metrics first, rather than focusing on AI initially.
- **Reason:** AI insights are only as good as the underlying data. Validated metrics provide the ground truth.
- **Expected benefit:** Trustworthy platform with provable metric accuracy.

### AI only summarizes precomputed metrics
- **Decision:** AI acts strictly as an explanation layer over precomputed metrics.
- **Reason:** Prevents AI hallucinations from generating incorrect data metrics.
- **Expected benefit:** Users get the benefit of natural language summaries without losing confidence in the numbers.
