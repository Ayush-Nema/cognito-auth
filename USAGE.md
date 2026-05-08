# Usage: Integrating cognito-auth with another FastAPI app

This document explains how to use cognito-auth alongside (or inside) another FastAPI application. If you only want to run cognito-auth on its own, see [README.md](./README.md).

---

## How it fits together

cognito-auth is the **issuer/orchestrator** of auth flows — it handles signup, login, refresh, and password reset by talking to AWS Cognito on behalf of clients. The JWTs it returns are signed by **AWS Cognito directly**, not by cognito-auth.

That matters: any other service pointed at the same Cognito user pool can verify those tokens independently. There is no shared secret with cognito-auth, no callback, and no library coupling required. **The integration boundary is the JWT itself.**

```
┌──────────┐   POST /login    ┌──────────────┐   cognito-idp   ┌─────────┐
│  client  │─────────────────▶│ cognito-auth │────────────────▶│ Cognito │
│          │◀─────────────────│              │◀────────────────│         │
└──────────┘    {id_token}    └──────────────┘    tokens       └─────────┘
     │
     │ Authorization: Bearer <id_token>
     ▼
┌──────────────────┐   fetches JWKS once   ┌─────────┐
│ your-other-app   │──────────────────────▶│ Cognito │
│ (FastAPI)        │◀──────────────────────│  JWKS   │
└──────────────────┘     public keys       └─────────┘
```

Two integration patterns are supported:

- **Pattern A (recommended):** run cognito-auth as a separate service; your other app verifies tokens independently.
- **Pattern B:** embed cognito-auth into your other FastAPI app as a single deployable.

---

## Pattern A — cognito-auth as a separate service

This is the standard microservice shape and what cognito-auth was built for.

### 1. Configure both services with the same Cognito identifiers

In `cognito-auth/configs/configs.yaml`:

```yaml
aws:
  region: us-east-1
cognito:
  user_pool_id: us-east-1_xxxxx
  client_id: <your client id>
```

In your other FastAPI app, set the same `user_pool_id`, `client_id`, and `region` (env vars, secrets manager, or config file — your call). The tokens are interoperable **only** because both services point at the same pool/client.

### 2. Run cognito-auth

```bash
cd cognito-auth
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Clients call `POST /api/v1/signup`, `POST /api/v1/login`, etc. on cognito-auth directly. Your other app never proxies these.

### 3. Add a JWT-verification dependency to your other app

Drop this file into your other FastAPI app. It does not import cognito-auth:

```python
# your_other_app/auth.py
import time
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

REGION = "us-east-1"
USER_POOL_ID = "us-east-1_xxxxx"
CLIENT_ID = "<your client id>"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_TTL = 3600
_bearer = HTTPBearer()


def _jwks() -> list[dict]:
    if _jwks_cache["keys"] is None or time.time() - _jwks_cache["fetched_at"] > _TTL:
        _jwks_cache["keys"] = httpx.get(JWKS_URL, timeout=5).json()["keys"]
        _jwks_cache["fetched_at"] = time.time()
    return _jwks_cache["keys"]


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    token = creds.credentials
    try:
        kid = jwt.get_unverified_header(token)["kid"]
        key = next(k for k in _jwks() if k["kid"] == kid)
        claims = jwt.decode(
            token, key, algorithms=["RS256"],
            audience=CLIENT_ID, issuer=ISSUER,
        )
        if claims.get("token_use") != "id":
            raise ValueError("expected id token")
        return claims
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")
```

Required deps in your other app: `fastapi`, `python-jose[cryptography]`, `httpx`.

### 4. Protect your endpoints

```python
from fastapi import FastAPI, Depends
from your_other_app.auth import get_current_user

app = FastAPI()


@app.get("/orders")
def list_orders(user: dict = Depends(get_current_user)):
    return {"email": user["email"], "orders": [...]}
```

Clients send `Authorization: Bearer <id_token>` on every request. The dependency returns 401 for missing/invalid/expired tokens, and provides decoded claims (`email`, `sub`, etc.) to your route on success.

### 5. Token refresh

Stays with cognito-auth. When an id token expires (default 1 hour), the client calls `POST /api/v1/refresh` on cognito-auth with its refresh token and receives a new id+access token. Your other app never touches the refresh flow.

---

## Pattern B — embed cognito-auth into one combined app

Use this when you want one deployable that bundles signup/login alongside your business endpoints.

The simplest approach is `app.mount(...)`, which runs cognito-auth as a sub-application under a path prefix:

```python
# your_combined_app/main.py
from fastapi import FastAPI, Depends

from app.main import app as auth_app                  # cognito-auth's FastAPI instance
from app.core.security import get_current_user        # reuse cognito-auth's verifier

main_app = FastAPI()
main_app.mount("/auth", auth_app)                     # /auth/api/v1/login, etc.


@main_app.get("/orders")
def list_orders(user=Depends(get_current_user)):
    return {"email": user.email, "orders": [...]}
```

For this to work, cognito-auth's source must be importable from your combined app's environment. Two ways:

1. **Path dependency in `pyproject.toml`:**
   ```toml
   dependencies = [
       "cognito-auth @ file:///abs/path/to/cognito-auth",
   ]
   ```
2. **Sibling repo + `sys.path` tweak** (development only): add cognito-auth's directory to `sys.path` before importing.

### Trade-offs

| Pro | Con |
|---|---|
| Single process, single Dockerfile, single deploy | Package-name collision: cognito-auth's package is `app`, which conflicts if your other repo also has an `app/`. You'll need to rename one, or rely on import order. |
| Same `get_current_user` reused by both halves | Middleware (GZip, TrustedHost, X-Process-Time, Cache-Control) only applies under the mounted prefix; your main app needs its own. |
| Easier local dev — one command | Tighter build-time coupling. Auth changes redeploy your business app. |

If you don't need a single deployable, **prefer Pattern A.**

---

## Deployment shapes

| Shape | When to use | Notes |
|---|---|---|
| Two services, reverse proxy | Microservices, multiple downstream apps share one auth | nginx/ALB routes `/auth/*` → cognito-auth, `/*` → business API. Pattern A. |
| Sidecar | One business app, want auth co-located | Both processes in the same pod / compose service. Pattern A. |
| Single process | Small deployments, monorepo | Pattern B with `mount` or router-include. |
| Polyglot | Other app is not Python | Pattern A. Any RS256 JWT library + the JWKS URL is enough. |

JWKS URL for any Cognito pool:

```
https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/jwks.json
```

---

## What to share vs. duplicate

| Item | How to handle |
|---|---|
| `user_pool_id`, `client_id`, `region` | Share via config (env vars, shared YAML, Secrets Manager). The only true binding between services. |
| JWT verification logic (~30 lines) | **Copy** into each consumer service. Don't import cognito-auth for it — keeps services decoupled. |
| Auth routes (signup/login/etc.) | Live only in cognito-auth. Never reimplement in consumer services. |
| Repository/service/business-logic layers | Live only in cognito-auth. Internal to the auth service. |

**Rule of thumb:** if you can do it with just the JWT, do it with just the JWT. Reach for tighter coupling (mounting, importing modules) only when you've decided you want one deployable and accept the build-time coupling that comes with it.

---

## FAQ

**Do I need cognito-auth running for my other app to verify tokens?**
No. Once a client has an id token, your other app verifies it against Cognito's public JWKS — cognito-auth is not in the request path. cognito-auth is only needed for **issuing** flows (login, signup, refresh, password reset).

**Can my other app be in a different language?**
Yes. Anything that can do RS256 JWT verification and an HTTPS GET for the JWKS URL works. cognito-auth's role doesn't change.

**id token vs access token — which do I send to my other app?**
Use the **id token** with the snippet above (it carries `email`). Cognito's access token is for scope/group checks if you configure those. Pick one and have the verifier check `token_use` to ensure clients aren't sending the wrong one.

**Where should I put `user_pool_id` / `client_id` in production?**
- cognito-auth: `configs/configs.yaml`, or load from Secrets Manager via `app/utils/aws_utils.py::get_secret()`.
- Other app: env vars, or the same Secrets Manager entry. They are not secrets in the cryptographic sense, but treating them as deployment-managed config keeps the two services from drifting.

**How long do tokens last?**
Defaults: id token 1 hour, access token 1 hour, refresh token 30 days. All configurable in the Cognito User Pool app client settings.

**What happens when Cognito rotates its signing keys?**
cognito-auth's verifier and the snippet above both cache JWKS with a TTL (default 1 hour) and refetch on expiry. No restart required.

**Can multiple downstream apps share one cognito-auth?**
Yes — that's the point. Any number of services can verify tokens from the same pool. Add the verification snippet to each.
