---
name: trading-team
description: Multi-agent stock analysis team (bull/bear researchers debate, analysts report, trader decides). Use for stock research, trade thesis, portfolio risk review. Paper/seminar use — not financial advice, never auto-trade.
---

# Trading Team (from TauricResearch/TradingAgents, Apache-2.0)

Analyst team that debates both sides before a trader acts:

- `analysts/` — market_analyst, news_analyst, sentiment_analyst, fundamentals_analyst
- `researchers/` — bull_researcher vs bear_researcher (opposing thesis)
- `managers/` — research_manager, portfolio_manager
- `risk_mgmt/` — aggressive/conservative/neutral debators
- `trader/` — final decision maker

Porter flow for "research this stock": read the analyst prompts for the method,
use web_search/fetch_url tools for live data, present bull vs bear, end with a
thesis + risks. Never place real orders.
