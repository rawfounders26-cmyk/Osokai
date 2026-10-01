"""Osok-AI Agent Benchmark — 100 real-world tasks, 8 categories.

Each task: {id, category, prompt, expect: {tools_any, approval, kinds_any}}.
PLAN mode (offline, CI-safe): propose()+validate() each task, check expected
tools/actions appear and approval flags are right. LIVE mode (opt-in, key +
budget): run through the agent loop, record success/steps/cost/interventions.
"""
import re

CATEGORIES = ("browser", "research", "email_calendar", "coding", "personal",
              "bills", "wardrobe", "social", "long_running")

# (id, category, prompt, expected tools (any-of), approval expected?)
TASKS = [
# --- browser (12) ---
("b01", "browser", "Open YouTube and play lo-fi music", ["open_url"], False),
("b02", "browser", "Search Google for the capital of Telangana", ["web_search", "open_url"], False),
("b03", "browser", "Fetch the Hacker News front page and summarize top stories", ["fetch_page", "web_search"], False),
("b04", "browser", "Open amazon.in and find wireless earbuds under 2000", ["open_url", "web_search"], False),
("b05", "browser", "Check train running status for Charminar Express", ["fetch_page", "web_search"], False),
("b06", "browser", "Open my Gmail inbox and count unread mail", ["open_url"], False),
("b07", "browser", "Find the cheapest flight Hyderabad to Goa next Friday", ["web_search", "fetch_page"], False),
("b08", "browser", "Look up today's gold rate in Hyderabad", ["web_search"], False),
("b09", "browser", "Open the Osokai GitHub repo page", ["open_url"], False),
("b10", "browser", "Find a highly rated biryani place near Madhapur", ["web_search"], False),
("b11", "browser", "Check the weather in Hyderabad for tomorrow", ["web_search"], False),
("b12", "browser", "Download the TSRTC bus timetable PDF", ["fetch_page", "open_url"], False),
# --- research (14) ---
("r01", "research", "Research the top 5 note-taking apps with pricing", ["research", "web_search"], False),
("r02", "research", "Compare Zerodha vs Groww brokerage charges", ["research"], False),
("r03", "research", "Deep dive on ONDC and how sellers join", ["research"], False),
("r04", "research", "What is the current repo rate and who sets it", ["web_search", "research"], False),
("r05", "research", "Summarize my workspace notes about the product launch", ["rag_ask"], False),
("r06", "research", "Find my document about tax filing", ["rag_ask"], False),
("r07", "research", "Research competitors for a tiffin delivery startup", ["research"], False),
("r08", "research", "What documents are needed for a new passport", ["web_search"], False),
("r09", "research", "Compare mutual fund vs PPF returns over 10 years", ["research"], False),
("r10", "research", "Find statistics on UPI transaction growth 2025", ["web_search", "research"], False),
("r11", "research", "What are the best areas to live in Hyderabad under 25k rent", ["research"], False),
("r12", "research", "Explain how home loan prepayment works", ["web_search"], False),
("r13", "research", "Find reviews of the Samsung M35 phone", ["web_search"], False),
("r14", "research", "Build a report on EV two-wheeler prices in India", ["research"], False),
# --- email_calendar (12) ---
("e01", "email_calendar", "Schedule a dentist appointment tomorrow 5pm", ["cal_add"], False),
("e02", "email_calendar", "What meetings do I have today", ["cal_list"], False),
("e03", "email_calendar", "Draft an email to Rahul about the delayed launch", ["email_compose"], True),
("e04", "email_calendar", "Cancel my 3pm meeting on Friday", ["cal_list"], False),
("e05", "email_calendar", "Send the weekly report to my manager", ["email_compose"], True),
("e06", "email_calendar", "Remind me to call mom at 8pm", ["loop_add"], False),
("e07", "email_calendar", "Block Saturday morning for deep work", ["cal_add"], False),
("e08", "email_calendar", "Draft a leave application for next Monday", ["email_compose"], True),
("e09", "email_calendar", "When is my next free 2-hour slot", ["cal_list"], False),
("e10", "email_calendar", "Reschedule lunch with Priya to Thursday", ["cal_add", "cal_list"], False),
("e11", "email_calendar", "Wish my team happy Diwali over email", ["email_compose"], True),
("e12", "email_calendar", "Create a packing checklist reminder for Goa", ["loop_add"], False),
# --- coding (12) ---
("c01", "coding", "Write a Python function to parse CSV bills", ["write_file", "shell"], False),
("c02", "coding", "Run the test suite in my workspace project", ["run_tests", "shell"], False),
("c03", "coding", "Create a folder for the new client project", ["make_dir"], False),
("c04", "coding", "Check git status of my workspace repo", ["git"], False),
("c05", "coding", "Build a landing page for my bakery", ["write_file"], False),
("c06", "coding", "Write a script to rename all photos by date", ["write_file", "shell"], False),
("c07", "coding", "Debug why my Python script crashes on empty input", ["shell", "read_file"], False),
("c08", "coding", "Create a monthly budget spreadsheet", ["make_xlsx"], False),
("c09", "coding", "Make a pitch deck outline for my startup", ["make_pptx"], False),
("c10", "coding", "Generate a logo concept for a chai brand", ["img_generate"], False),
("c11", "coding", "Resize my banner image to 1200 wide", ["img_op"], False),
("c12", "coding", "Save 3 reference photos of office interiors", ["save_images"], False),
# --- personal (14) ---
("p01", "personal", "Remember that I am vegetarian", ["pref_add"], False),
("p02", "personal", "My name is Arjun and I live in Hyderabad", ["profile_set"], False),
("p03", "personal", "What is my monthly budget", ["profile_get"], False),
("p04", "personal", "Plan my outfits for the week", ["outfit_suggest"], False),
("p05", "personal", "What should I wear to a wedding tomorrow", ["outfit_suggest"], False),
("p06", "personal", "Add blue linen shirt to wardrobe", ["wardrobe_add"], False),
("p07", "personal", "I wore the black jeans yesterday", ["wardrobe_list"], False),
("p08", "personal", "Pack for 4 days in Goa", ["outfit_suggest"], False),
("p09", "personal", "Track my gym habit daily", ["loop_add"], False),
("p10", "personal", "Remind me to pay rent on the 1st every month", ["loop_add"], False),
("p11", "personal", "My UPI id is arjun@okhdfc", ["profile_set"], False),
("p12", "personal", "What did we discuss about the launch yesterday", ["rag_ask"], False),
("p13", "personal", "Summarize my open loops", ["loop_due"], False),
("p14", "personal", "Mark the dentist loop as done", ["loop_done"], False),
# --- bills (12) ---
("f01", "bills", "Split 1200 for dinner with flatmates", ["bill_expense"], False),
("f02", "bills", "Who owes whom in the flat group", ["bill_balances"], False),
("f03", "bills", "Settle up the Goa trip group", ["bill_settle"], False),
("f04", "bills", "Create a bill group for the office team", ["bill_group"], False),
("f05", "bills", "Show all my bill groups", ["bill_groups"], False),
("f06", "bills", "Add a 9000 rent expense paid by me", ["bill_expense"], False),
("f07", "bills", "Repeat the internet bill monthly", ["bill_expense", "loop_add"], False),
("f08", "bills", "House ledger for this month", ["bill_balances"], False),
("f09", "bills", "Record that Ravi paid me 500", ["bill_settle"], False),
("f10", "bills", "How much do I owe across all groups", ["bill_balances"], False),
("f11", "bills", "Split cab fare 450 three ways", ["bill_expense"], False),
("f12", "bills", "Set my UPI id for faster settling", ["profile_set"], False),
# --- wardrobe (10) ---
("w01", "wardrobe", "Suggest an outfit for office today", ["outfit_suggest"], False),
("w02", "wardrobe", "What should I wear to the gym", ["outfit_suggest"], False),
("w03", "wardrobe", "List everything in my wardrobe", ["wardrobe_list"], False),
("w04", "wardrobe", "Add white sneakers to wardrobe", ["wardrobe_add"], False),
("w05", "wardrobe", "Is it kurta weather today", ["outfit_suggest", "web_search"], False),
("w06", "wardrobe", "Plan office looks for the whole week", ["outfit_suggest"], False),
("w07", "wardrobe", "What did I wear last Monday", ["wardrobe_list"], False),
("w08", "wardrobe", "Suggest a formal outfit for an interview", ["outfit_suggest"], False),
("w09", "wardrobe", "Add a navy blazer for winter weddings", ["wardrobe_add"], False),
("w10", "wardrobe", "Laundry is done, reset my wardrobe", ["wardrobe_list"], False),
# --- social (6) ---
("s01", "social", "Post launch day on X", ["social_draft"], True),
("s02", "social", "Post our hiring news on LinkedIn", ["social_draft"], True),
("s03", "social", "Draft a product announcement for social", ["social_draft"], False),
("s04", "social", "Show my recent social posts", ["social_draft"], False),
("s05", "social", "Announce the Diwali sale mock", ["social_draft"], True),
("s06", "social", "Which platform fits a hiring update, LinkedIn or X", ["social_draft"], False),
# --- long_running (14) ---
("l01", "long_running", "Track Samsung M35 price for 30 days and alert on drops", ["loop_add", "web_search"], False),
("l02", "long_running", "Monitor my startup competitors and brief me weekly", ["research", "loop_add"], False),
("l03", "long_running", "Prepare my company for fundraising", ["research", "email_compose"], False),
("l04", "long_running", "Plan a 7-day Singapore trip under 1.5 lakh", ["research", "trip_plan"], False),
("l05", "long_running", "Organize my wedding over the next 6 months", ["research", "cal_add"], False),
("l06", "long_running", "Learn Python well enough to build small apps", ["write_file", "web_search"], False),
("l07", "long_running", "Get our website redesign completed this quarter", ["research", "loop_add"], False),
("l08", "long_running", "Build a five-person sales team", ["research", "email_compose"], False),
("l09", "long_running", "Create our operating budget for next year", ["make_xlsx", "research"], False),
("l10", "long_running", "Find a new apartment in Hyderabad under 25k", ["web_search", "loop_add"], False),
("l11", "long_running", "Launch my online bakery store", ["write_file", "research"], False),
("l12", "long_running", "Migrate our blog to the new domain without losing SEO", ["seo_check", "research"], False),
("l13", "long_running", "Prepare everything for the board meeting Friday", ["research", "make_pptx"], False),
("l14", "long_running", "Resolve the customer complaint about billing", ["email_compose", "rag_ask"], True),
]


def _words(text: str):
    import re as _re
    return set(_re.findall(r"[a-z]{3,}", (text or "").lower()))


def categories():
    return list(CATEGORIES)


def count():
    return len(TASKS)
