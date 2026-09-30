"""Browser takeover console — see + inspect the VM browser from Command Port.
Backed by the browser-use CLI (Python over stdin, persistent session)."""
import os, subprocess

def _pipe(code: str, timeout: int = 90) -> str:
    try:
        r = subprocess.run("browser-use", shell=True, input=code,
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + ("\nERR:" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        return "(timed out)"
    except Exception as e:
        return f"(error: {e})"

def state() -> str:
    return _pipe("ensure_real_tab()\nprint(page_info())")[:6000]

def screenshot() -> str:
    """Returns PNG path (workspace) of the live browser.
    Needs one-time Chrome approval: tick 'Allow remote debugging' on the chrome://inspect popup."""
    import time
    try:
        from app.paths import ws as _pws
    except ImportError:
        from paths import ws as _pws
    ws = _pws()
    fp = os.path.join(ws, f"console-{int(time.time())}.png")
    out = _pipe(f"ensure_real_tab()\nshot('{fp}')\nprint('saved')")
    if os.path.isfile(fp):
        return fp
    return ""

def open(url: str) -> str:
    try:
        from app.system_tools import clean_url
    except ImportError:
        from system_tools import clean_url
    url = clean_url(url)
    return _pipe(f'new_tab("{url}")\nwait_for_load()\nprint(page_info())')[:4000]
