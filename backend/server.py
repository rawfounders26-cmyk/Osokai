"""Osok-AI server entry — used by PyInstaller builds and `python server.py`."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8765, log_level="warning")
