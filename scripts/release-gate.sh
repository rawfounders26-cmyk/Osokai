#!/bin/sh
# Eval-gated release: pytest + docker build + import smoke must ALL pass.
# CI calls this; humans can run it before tagging. Any failure -> no release.
set -eu
cd "$(dirname "$0")/.."

echo "== evals =="
(cd backend && python -m pytest tests/ -q) || { echo "EVALS FAILED — release blocked"; exit 1; }

echo "== docker build =="
docker build -t osokai:gate . || { echo "DOCKER BUILD FAILED — release blocked"; exit 1; }

echo "== import smoke =="
docker run --rm -e OSOKAI_AUTH_TOKEN=gate-check osokai:gate \
  python -c "import app.main, app.e2e, app.slm, app.wake, app.optimizer, app.digest; print('import ok')" \
  || { echo "SMOKE FAILED — release blocked"; exit 1; }

echo "RELEASE GATE GREEN"
