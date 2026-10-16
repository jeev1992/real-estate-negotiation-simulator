"""
Pricing MCP Server — demo authentication (signed JWTs)
========================================================
Shared by `pricing_server.py --http` (which VERIFIES tokens) and the command
line below (which MINTS them). In production the minting side is an identity
provider (Entra ID, Auth0, ...) and the server only ever verifies; here one
shared secret plays both roles so the whole flow fits on a laptop.

Token = HS256-signed JWT with these claims:
    sub    who the caller is (e.g. "buyer-agent")
    scope  space-separated permissions, e.g. "pricing:read pricing:analyze"
    iss    who issued it            (must equal ISSUER)
    aud    which server it is for   (must equal AUDIENCE)
    exp    expiry time

Roles (what each token is allowed to do):
    guest    no scopes                       → rejected by the server (403)
    buyer    pricing:read                    → get_market_price only
    analyst  pricing:read pricing:analyze    → both tools

Mint a token:
    python m1_mcp/pricing_auth.py --role buyer                 # print it
    python m1_mcp/pricing_auth.py --role analyst --write-env   # save as PRICING_MCP_TOKEN in .env

Requires PRICING_JWT_SECRET in .env (see .env.example).
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import jwt
from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken, TokenVerifier

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _REPO_ROOT / ".env"
load_dotenv(_ENV_FILE)

ISSUER = "https://auth.real-estate-workshop.example"
AUDIENCE = "real-estate-pricing-mcp"
ALGORITHM = "HS256"

SCOPE_READ = "pricing:read"
SCOPE_ANALYZE = "pricing:analyze"

ROLES: dict[str, list[str]] = {
    "guest": [],
    "buyer": [SCOPE_READ],
    "analyst": [SCOPE_READ, SCOPE_ANALYZE],
}


def load_secret() -> str:
    secret = os.environ.get("PRICING_JWT_SECRET", "").strip()
    if len(secret) < 32 or secret.startswith("replace-with"):
        raise SystemExit(
            "PRICING_JWT_SECRET is missing, too short (<32 chars), or still the .env.example "
            "placeholder. Set a random one in .env: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return secret


def mint_token(subject: str, scopes: list[str], ttl_minutes: int = 480) -> str:
    """Create a signed token — the job an identity provider does in production."""
    now = int(time.time())
    claims = {
        "sub": subject,
        "scope": " ".join(scopes),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + ttl_minutes * 60,
    }
    return jwt.encode(claims, load_secret(), algorithm=ALGORITHM)


class JwtTokenVerifier(TokenVerifier):
    """Authentication: accept a bearer token only if it is genuinely ours.

    Checks the signature, expiry, issuer and audience. Returning None makes the
    MCP server answer 401 before any tool code runs.
    """

    def __init__(self) -> None:
        self._secret = load_secret()

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            print(f"[auth] rejected token: {type(error).__name__}", file=sys.stderr)
            return None
        return AccessToken(
            token=token,
            client_id=claims["sub"],
            scopes=claims.get("scope", "").split(),
            expires_at=claims["exp"],
        )


def _write_env(name: str, value: str) -> None:
    text = _ENV_FILE.read_text(encoding="utf-8") if _ENV_FILE.exists() else ""
    line = f"{name}={value}"
    if re.search(rf"^{name}=.*$", text, flags=re.M):
        text = re.sub(rf"^{name}=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    _ENV_FILE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mint a demo JWT for the pricing MCP server.")
    parser.add_argument("--role", choices=sorted(ROLES), required=True)
    parser.add_argument("--minutes", type=int, default=480, help="Lifetime in minutes (default: 8 hours)")
    parser.add_argument("--write-env", action="store_true", help="Save it to .env as PRICING_MCP_TOKEN")
    args = parser.parse_args()

    token = mint_token(subject=f"{args.role}-agent", scopes=ROLES[args.role], ttl_minutes=args.minutes)
    if args.write_env:
        _write_env("PRICING_MCP_TOKEN", token)
        article = "an" if args.role[0] in "aeiou" else "a"
        print(f"Saved {article} {args.role} token (scopes: {' '.join(ROLES[args.role]) or 'none'}, "
              f"valid {args.minutes} min) to .env as PRICING_MCP_TOKEN. Restart adk web to use it.")
    else:
        print(token)
