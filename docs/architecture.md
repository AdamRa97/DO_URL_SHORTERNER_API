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

## Request Lifecycle — Authentication

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI (API)
    participant DB as PostgreSQL

    Note over C,DB: Login — POST /api/v1/tokens
    C->>A: POST /api/v1/tokens {email, password}
    A->>DB: SELECT * FROM users WHERE email = ?
    DB-->>A: user row (or null)
    Note over A: verify_password(password, hashed_password)<br/>Any failure → same uniform 401 (no oracle)
    A->>DB: INSERT INTO refresh_tokens (jti, user_id, expires_at)
    A-->>C: 200 {access_token, refresh_token, token_type}

    Note over C,DB: Refresh — PUT /api/v1/tokens
    C->>A: PUT /api/v1/tokens {refresh_token}
    Note over A: decode_token() → verify type == "refresh" + extract jti
    A->>DB: SELECT * FROM refresh_tokens WHERE jti = ?
    Note over A: check revoked == false
    A->>DB: SELECT * FROM users WHERE id = stored.user_id
    A-->>C: 200 {access_token}

    Note over C,DB: Logout — DELETE /api/v1/tokens
    C->>A: DELETE /api/v1/tokens {refresh_token} + Bearer header
    Note over A: decode_token() → extract jti<br/>(silently returns if token already invalid)
    A->>DB: UPDATE refresh_tokens SET revoked=true WHERE jti = ?
    A-->>C: 204 No Content
```

## Request Tracing (RequestIDMiddleware)

Every HTTP request is assigned a unique trace ID. This ID flows through the entire request lifecycle, appearing in every JSON log line so a single request can be correlated across all log output.

```
Incoming request
     │
     ▼
RequestIDMiddleware
  ├─ Read X-Request-ID header (if present)
  └─ Generate UUID4 (if header absent)
         │
         ▼
  Set request_id_var ContextVar  ──► all log lines include request_id
         │
         ▼
  Call next handler (routers, services, repos)
         │
         ▼
  Add X-Request-ID header to response
         │
         ▼
  Reset ContextVar (cleanup)
```

The `X-Request-ID` header is echoed back in every response, making it easy for API clients and load balancers to correlate responses with their originating requests.

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
