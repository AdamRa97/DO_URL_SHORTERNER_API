# Architecture

## Request Lifecycle — Redirect (Core Flow)

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI (API)
    participant R as Redis (Cache)
    participant DB as PostgreSQL
    participant W as Celery Worker

    C->>A: GET /{alias}
    A->>R: GET redirect:{alias}
    alt Cache Hit
        R-->>A: original_url
        A-->>C: 302 → original_url
    else Cache Miss
        A->>DB: SELECT * FROM links WHERE alias = ?
        DB-->>A: link row (or null)
        alt Link not found or expired
            A-->>C: 404 Not Found
        else Link valid
            A->>R: SETEX redirect:{alias} {ttl} {original_url}
            A-->>C: 302 → original_url
        end
    end
    A-)W: record_click.delay(alias, ip_hash, user_agent, referer)
    W->>DB: INSERT INTO clicks (...)
```

## Request Lifecycle — Create Short Link

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI (API)
    participant RL as Rate Limiter (Redis)
    participant DB as PostgreSQL

    C->>A: POST /api/v1/links {original_url, custom_alias?}
    A->>RL: Check rate limit (Fixed Window, per IP)
    alt Limit exceeded
        RL-->>A: Over limit
        A-->>C: 429 Too Many Requests + Retry-After
    else Within limit
        Note over A: Validate Bearer JWT → extract user_id + role
        alt Custom alias provided
            A->>DB: SELECT alias WHERE alias = custom_alias
            alt Alias taken
                A-->>C: 409 Conflict
            else Available
                A->>DB: INSERT INTO links (alias, original_url, owner_id, ...)
                DB-->>A: link row
                A-->>C: 201 Created {alias, original_url, ...}
            end
        else Auto-generate alias
            loop Up to 5 retries
                Note over A: generate_alias() → base62 random code
                A->>DB: SELECT alias WHERE alias = generated
                alt Collision
                    Note over A: retry
                else Unique
                    A->>DB: INSERT INTO links (...)
                    DB-->>A: link row
                    A-->>C: 201 Created {alias, original_url, ...}
                end
            end
        end
    end
```

## Data Model

```
users
├── id             PK
├── email          UNIQUE INDEX
├── hashed_password
├── role           ENUM (user | admin)
└── created_at

links
├── id             PK
├── alias          UNIQUE INDEX
├── original_url
├── owner_id       FK → users.id
├── expires_at     NULLABLE
├── created_at
└── updated_at

clicks
├── id             PK
├── link_id        FK → links.id
├── ip_hash        SHA-256(raw_ip) — not PII
├── user_agent
├── referer
└── clicked_at     INDEX

refresh_tokens
├── id             PK
├── jti            UNIQUE INDEX (JWT ID)
├── user_id        FK → users.id
├── expires_at
└── revoked        BOOLEAN
```

## Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Client                           │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────────┐
│                    FastAPI (uvicorn)                     │
│  ┌─────────────┐  ┌───────────┐  ┌────────────────────┐ │
│  │  Middleware  │  │  Routers  │  │  Exception Handler │ │
│  │ RequestID   │  │ /api/v1/* │  │  (uniform errors)  │ │
│  │ Rate Limit  │  │ /{alias}  │  └────────────────────┘ │
│  └─────────────┘  └─────┬─────┘                         │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐    │
│  │              Services Layer                     │    │
│  │  auth · user · link · analytics                 │    │
│  └──────────┬──────────────────────────────────────┘    │
│             │                                           │
│  ┌──────────▼──────────────────────────────────────┐    │
│  │            Repositories Layer                   │    │
│  │  user_repo · link_repo · click_repo · token_repo│    │
│  └──────────┬──────────────────────────────────────┘    │
└─────────────┼───────────────────────────────────────────┘
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
PostgreSQL  Redis     Celery Worker
(persistent) (cache/   (async click
             broker)    recording)
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Always create new alias for duplicate URLs | Requirement: each POST creates a fresh link, regardless of original_url |
| Cache-aside pattern for redirects | Redis hit avoids DB query on the hottest path |
| Cache eviction on delete/update | Synchronous eviction prevents stale redirects |
| 404 (not 403) for other user's link | Prevents resource enumeration by bad actors |
| Uniform 401 on all auth failures | Prevents username/password oracle attacks |
| SHA-256(ip) stored, not raw IP | GDPR-friendly: pseudonymised click data |
| Redirect router registered last | Prevents `/{alias}` catch-all from shadowing `/api/v1/*` |
| Celery uses sync SQLAlchemy (psycopg2) | Celery workers are synchronous; asyncpg cannot be used |
