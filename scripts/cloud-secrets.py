"""Generate production secrets into backend/.env (run once per machine).
Keeps dev and cloud values separate: never commits, never prints existing keys."""
import os
import secrets
import sys

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend"))
ENV = os.path.join(BASE, ".env")


def _gen(prefix: str, nbytes: int = 24) -> str:
    return prefix + secrets.token_urlsafe(nbytes)


def main() -> None:
    lines = []
    if os.path.isfile(ENV):
        with open(ENV, encoding="utf-8") as f:
            lines = f.read().splitlines()
    have = {}
    for ln in lines:
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            have[k.strip()] = v.strip()
    changed = False
    if not have.get("OSOKAI_AUTH_TOKEN"):
        lines.append(f"OSOKAI_AUTH_TOKEN={_gen('osokai_')}")
        changed = True
    if not have.get("OSOKAI_RELAY_KEY"):
        lines.append(f"OSOKAI_RELAY_KEY={_gen('relay_')}")
        changed = True
    if changed:
        with open(ENV, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"secrets written to {ENV} (existing keys untouched)")
    else:
        print("secrets already present — nothing changed")


if __name__ == "__main__":
    sys.exit(main())
