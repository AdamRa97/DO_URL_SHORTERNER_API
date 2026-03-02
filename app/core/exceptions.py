from fastapi import Request
from fastapi.responses import JSONResponse


# --- Custom exception types ---

class AliasConflictError(Exception):
    """Raised when a requested custom alias is already taken."""


class LinkNotFoundError(Exception):
    """Raised when an alias does not exist or the caller is not permitted to see it."""


class AuthenticationError(Exception):
    """Raised on any authentication failure (always maps to a generic 401)."""


class AuthorizationError(Exception):
    """Raised when an authenticated user lacks the required role."""


class AliasValidationError(ValueError):
    """Raised when a custom alias fails format validation."""


# --- FastAPI exception handlers ---

async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Insufficient permissions"},
    )


async def link_not_found_handler(request: Request, exc: LinkNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"},
    )


async def alias_conflict_handler(request: Request, exc: AliasConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "This alias is already taken. Please choose a different one."},
    )


async def alias_validation_error_handler(
    request: Request, exc: AliasValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )
