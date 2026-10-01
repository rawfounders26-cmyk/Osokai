"""Generate production secrets into backend/.env (run once per machine).
Keeps dev and cloud values separate: never commits, never prints existing keys."""
import os
import secrets
import sys

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend"))
ENV = os.path.join(BASE, ".env")


PLACEHOLDER_MARKS = ("paste-", "paste_", "example", "changeme", "xxx", "your-", "your_", "todo")


def _gen(prefix: str, nbytes: int = 24) -> str:
    return prefix + secrets.token_urlsafe(nbytes)


def _bad(v: str) -> bool:
    v = (v or "").strip()
    if len(v) < 20:
        return True
    return any(m in v.lower() for m in PLACEHOLDER_MARKS)


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
    for key, prefix in (("OSOKAI_AUTH_TOKEN", "osokai_"), ("OSOKAI_RELAY_KEY", "relay_")):
        if _bad(have.get(key, "")):
            lines = [ln for ln in lines if not ln.strip().startswith(key + "=")]
            lines.append(f"{key}={_gen(prefix)}")
            changed = True
    if changed:
        with open(ENV, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"secrets written to {ENV} (placeholders replaced, real keys untouched)")
    else:
        print("secrets already present — nothing changed")


if __name__ == "__main__":
    sys.exit(main())
