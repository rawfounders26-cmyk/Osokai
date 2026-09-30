"""bill-watcher — built by Osok-AI. Purpose: nudge on overdue debts"""
TOOLS = ['bill_balances']

def run(task: str) -> str:
    """Entry point: sub-agent receives a task string."""
    return f"bill-watcher ready. Tools: {TOOLS}. Task received: {task}"
