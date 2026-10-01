"""Intent fast-path — deterministic, completes in milliseconds. No LLM needed.
Extension content scripts finish web tasks (e.g. YouTube auto-plays first result)."""
import re, urllib.parse

try:
    from app.system_tools import open_app, open_url
except ImportError:
    from system_tools import open_app, open_url

YOUTUBE_SITES = ("youtube", "yt")

def _yt_search_url(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)

def _google_url(query: str, images: bool = False) -> str:
    u = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    return u + ("&tbm=isch" if images else "")

_TA_VERBS = [("thira", "open"), ("thirakkavum", "open"), ("திற", "open"),
              ("podu", "play"), ("podunga", "play"), ("podavum", "play"), ("போடு", "play"),
              ("thedu", "search"), ("thedavum", "search"), ("தேடு", "search"),
              ("anuppu", "send"), ("அனுப்பு", "send"), ("paaru", "watch"), ("பாரு", "watch")]

def _tamil_fix(t: str) -> str:
    """Tanglish/Tamil SOV ('youtube thira') -> English SVO ('open youtube')."""
    if re.match(r"^(open|play|watch|search|find|send|add|remind|done|track|list|show)", t):
        return t
    for ta, en in _TA_VERBS:
        if ta in t:
            t = en + " " + t.replace(ta, "").strip()
            break
    return re.sub(r"\s+", " ", t).strip()

def parse(message: str):
    """Return (action_dict, reply) or (None, None) if no fast intent."""
    t = _tamil_fix(message.strip().lower())

    # loops: "remind me to reply to ravi tomorrow 5pm" / "done replying to ravi"
    m = re.match(r"^remind me to\s+(.+)$", t)
    if m:
        return {"type": "loop_add", "title": m.group(1).strip()}, None
    m = re.match(r"^(?:done|finished|completed)\s+(.+)$", t)
    if m and len(m.group(1).split()) <= 8:
        return {"type": "loop_done", "text": m.group(1).strip()}, None

    # play/watch <anything> [on youtube] — songs AND episodes/videos
    m = re.match(r"^(?:play|watch|play the|watch the)\s+(.+?)(?:\s+on\s+(youtube|yt))?$", t)
    if m:
        q = m.group(1).strip()
        url = _yt_search_url(q)
        return {"type": "youtube_play", "query": q, "url": url}, None

    # open youtube and play/watch <anything>
    m = re.match(r"^open\s+(youtube|yt)\s+and\s+(?:play|watch)\s+(.+)$", t)
    if m:
        q = m.group(2).strip()
        url = _yt_search_url(q)
        return {"type": "youtube_play", "query": q, "url": url}, None

    # open youtube [search X]
    m = re.match(r"^open\s+(youtube|yt)(?:\s+(?:and\s+)?search\s+(.+))?$", t)
    if m:
        q = (m.group(2) or "").strip()
        url = _yt_search_url(q) if q else "https://www.youtube.com"
        return {"type": "open_url", "url": url}, None

    # open google and search <q> and save <n> image(s) on desktop
    m = re.match(r"^open google and search\s+(.+?)\s+and\s+save\s+(\d+)?\s*images?\s+(?:on|to)\s+(desktop|downloads)?$", t)
    if m:
        q = m.group(1).strip()
        return {"type": "search_save_images", "query": q,
                "url": _google_url(q, images=True),
                "count": int(m.group(2) or 1), "dest": m.group(3) or "desktop"}, None

    # open google and search <q> — new Chrome tab with Google results
    m = re.match(r"^open\s+google\s+and\s+search\s+(.+)$", t)
    if m:
        return {"type": "open_url", "url": _google_url(m.group(1).strip())}, None

    # open <something> images [on google] — e.g. "open dog images", "open god images on google"
    m = re.match(r"^open\s+(.+?)\s+images?(?:\s+on\s+(google))?$", t)
    if m:
        q = m.group(1).strip()
        return {"type": "open_url", "url": _google_url(q, images=True)}, None

    # India everyday: blinkit/swiggy/zomato/bookmyshow/irctc/amazon
    m = re.match(r"^open\s+(blinkit|swiggy|zomato|bookmyshow|irctc|amazon)(\s|$)", t)
    if m:
        sites = {"blinkit": "https://blinkit.com", "swiggy": "https://www.swiggy.com",
                 "zomato": "https://www.zomato.com", "bookmyshow": "https://in.bookmyshow.com",
                 "irctc": "https://www.irctc.co.in", "amazon": "https://www.amazon.in"}
        return {"type": "open_url", "url": sites[m.group(1)]}, None

    # trackers: subscriptions, dentist waitlist, bill disputes -> watched goal + checklist
    m = re.match(r"^track\s+(.+)$", t)
    if m:
        return {"type": "track", "text": m.group(1).strip()}, None

    # road trips: "plan a road trip from chennai to pondicherry 2 days"
    try:
        from app.trip import parse_trip
    except ImportError:
        from trip import parse_trip
    tp = parse_trip(message)
    if tp:
        return {"type": "trip_plan", "origin": tp[0], "dest": tp[1], "days": tp[2]}, None

    # outfit planner: week plan / occasion look / pack / wore / laundry / add
    m = re.match(r"^(?:plan|organise|organize)(?: my)? (?:outfits|clothes)(?: for the week)?$", t)
    if m:
        return {"type": "outfit_plan"}, None
    m = re.match(r"^(?:what should i wear|what to wear|outfit for|wear to|dress for)(?: to| for)?\s+(.+?)(?:\s+(today|tomorrow|on \w+))?$", t)
    if m:
        return {"type": "outfit_occasion", "occasion": m.group(1).strip(), "day": (m.group(2) or "").strip()}, None
    m = re.match(r"^pack(?:ing)?(?: list)? for (\d+) days?(?: in (.+))?$", t)
    if m:
        return {"type": "outfit_pack", "days": int(m.group(1)), "dest": (m.group(2) or "").strip()}, None
    m = re.match(r"^(?:i )?wore (?:the )?(.+)$", t) or re.match(r"^log outfit:?\s+(.+)$", t)
    if m:
        return {"type": "outfit_wore", "item": m.group(1).strip()}, None
    if re.match(r"^laundry (?:done|day)$", t):
        return {"type": "outfit_laundry"}, None
    m = re.match(r"^add (.+?) to (?:my )?wardrobe$", t)
    if m:
        return {"type": "outfit_add", "desc": m.group(1).strip()}, None

    # social: draft/post + status (chat-driven, approval-gated publishes)
    m = re.match(r"^(?:post|share|publish|announce)\s+(.+?)\s+on\s+(x|twitter|linkedin|mock)$", t)
    if m:
        return {"type": "social_post", "text": m.group(1).strip(),
                "platform": ("x" if m.group(2) in ("x", "twitter") else m.group(2))}, None
    m = re.match(r"^(?:social status|my posts|post status)$", t)
    if m:
        return {"type": "social_status"}, None

    # tier-1 connectors: telegram send, github brief, free slots, invites
    m = re.match(r"^(?:telegram|tg|send telegram)\s+(.+?)\s+to\s+(\S+)$", t)
    if m:
        return {"type": "telegram_send", "text": m.group(1).strip(), "chat_id": m.group(2).strip()}, None
    m = re.match(r"^(?:github|gh)\s+(.+)$", t)
    if m:
        rest = m.group(1).strip()
        if "/" in rest.split()[0]:
            return {"type": "github_brief", "repo": rest.split()[0]}, None
        return {"type": "github_repos"}, None
    m = re.match(r"^(?:free slots|when am i free|free time)(?:\s+(today|tomorrow|\S+))?(?:\s+for\s+(?:(\d+)\s*min|an?\s*hour))?$", t)
    if m:
        mins = int(m.group(2) or 60) if m.group(2) else 60
        return {"type": "cal_free", "day": (m.group(1) or "").strip(), "mins": mins}, None
    m = re.match(r"^invite\s+(.+?)\s+to\s+(.+?)\s+(today|tomorrow|\S+)(?:\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?$", t)
    if m:
        return {"type": "cal_invite", "title": m.group(1).strip(), "attendees": m.group(2).strip(),
                "day": m.group(3).strip(), "time": (m.group(4) or "").strip()}, None

    # tier-2 connectors: razorpay/collect, whatsapp, youtube
    m = re.match(r"^(?:razorpay|rzp)?\s*collect\s+(\d[\d,]*)\s+from\s+(\S+)(?:\s+for\s+(.+))?$", t)
    if m:
        return {"type": "pay_collect", "amount": m.group(1).replace(",", ""),
                "upi": m.group(2).strip(), "note": (m.group(3) or "").strip()}, None
    m = re.match(r"^whatsapp\s+(.+?)\s+to\s+(\+\d{10,15})$", t)
    if m:
        return {"type": "wa_send", "text": m.group(1).strip(), "to": m.group(2).strip()}, None
    m = re.match(r"^(?:latest videos|new videos)(?: from| on)?\s+(.+)$", t)
    if m:
        return {"type": "yt_latest", "channel": m.group(1).strip()}, None
    m = re.match(r"^youtube\s+(https?://\S+|@\S+|[A-Za-z0-9_-]{10,})$", t)
    if m:
        return {"type": "yt_latest", "channel": m.group(1).strip()}, None

    # bills: quick split / settle up / recurring / house ledger
    m = re.match(r"^split (\d[\d,]*)\s+for\s+(.+?)\s+(?:with|in|among)\s+(.+)$", t)
    if m:
        return {"type": "bill_quick", "amount": m.group(1).replace(",", ""),
                "title": m.group(2).strip(), "group": m.group(3).strip()}, None
    m = re.match(r"^split (.+?)\s+(\d[\d,]*)(?:\s+(?:with|in|among)\s+(.+))?$", t)
    if m:
        return {"type": "bill_quick", "title": m.group(1).strip(), "amount": m.group(2).replace(",", ""),
                "group": (m.group(3) or "").strip()}, None
    m = re.match(r"^settle(?: up)?(?: (.+))?$", t)
    if m:
        return {"type": "bill_settle_up", "group": (m.group(1) or "").strip()}, None
    m = re.match(r"^repeat (.+?) (\d[\d,]*)\s+(monthly|weekly)(?: in (.+?))?(?: paid by (.+))?$", t)
    if m:
        return {"type": "bill_repeat", "title": m.group(1).strip(), "amount": m.group(2).replace(",", ""),
                "freq": m.group(3), "group": (m.group(4) or "").strip(),
                "paid_by": (m.group(5) or "me").strip()}, None
    m = re.match(r"^(?:house ledger|monthly (?:bills|ledger|summary))(?: for (.+))?$", t)
    if m:
        return {"type": "bill_house", "group": (m.group(1) or "").strip()}, None

    # open <app>
    m = re.match(r"^open\s+([a-z0-9 .+]+)$", t)
    if m:
        name = m.group(1).strip()
        if any(s in name for s in (".com", ".in", ".org", "www.", "http")) or " " not in name and "." in name:
            return {"type": "open_url", "url": name}, None
        if "youtube" in name:
            return {"type": "open_url", "url": "https://www.youtube.com"}, None
        if name in ("google", "gmail"):
            return {"type": "open_url", "url": "https://www.google.com" if name == "google" else "https://mail.google.com"}, None
        return {"type": "open_app", "app": name}, None

    # shopping browse FIRST (generic search below would shadow it): "search mens shoes under 2000"
    m = re.match(r"^(?:search|find|shop for|show me)\s+(.+?)(?:\s+(?:under|below|within|less than)\s+(?:rs\.?\s?|₹\s?)?([\d,]+))?$", t)
    if m:
        item, budget = m.group(1).strip(), (m.group(2) or "").replace(",", "")
        if "youtube" in item or item in ("yt",):
            pass  # fall through to youtube handler below
        elif any(w in item for w in ("shoe", "phone", "laptop", "watch", "shirt", "dress", "kurta", "saree", "tv", "headphone", "earbud", "camera", "tablet", "sandal", "bag", "suitcase", "mixer", "fridge", "ac ")) or budget:
            url = "https://www.flipkart.com/search?q=" + urllib.parse.quote_plus(item)
            return {"type": "shop_browse", "item": item, "budget": budget, "url": url}, None

    # generate image/picture of X — AI image generation into workspace/
    m = re.match(r"^(?:generate|create|make)\s+(?:an?\s+)?(?:image|picture|photo|wallpaper)\s+(?:of\s+)?(.+)$", t)
    if m:
        return {"type": "img_gen", "prompt": m.group(1).strip()}, None

    # search <q> on google / search <q>
    m = re.match(r"^(?:search|find|google)\s+(.+?)(?:\s+on\s+google)?$", t)
    if m:
        q = m.group(1).strip()
        if q and "youtube" not in q:
            images = any(w in q for w in ("image", "images", "photo", "photos", "picture", "wallpaper"))
            q = re.sub(r"\s*(images?|photos?|pictures?|wallpapers?)\s*", " ", q).strip()
            return {"type": "open_url", "url": _google_url(q or m.group(1).strip(), images=images)}, None
    m = re.match(r"^(?:search|find)\s+(.+?)\s+on\s+(youtube|yt)$", t)
    if m:
        return {"type": "open_url", "url": _yt_search_url(m.group(1).strip())}, None

    # images: resize/convert/compress/thumbnail/meme workspace files
    m = re.match(r"^(?:resize|shrink)\s+(.+?)\s+to\s+(\d+)(?:x(\d+))?$", t)
    if m:
        return {"type": "img", "op": "resize", "file": m.group(1).strip(),
                "w": int(m.group(2)), "h": int(m.group(3) or 0)}, None
    m = re.match(r"^convert\s+(.+?)\s+to\s+(png|jpg|jpeg|webp)$", t)
    if m:
        return {"type": "img", "op": "convert", "file": m.group(1).strip(), "fmt": m.group(2)}, None
    m = re.match(r"^compress\s+(.+?)(?:\s+(?:to\s+)?(\d+))?$", t)
    if m:
        return {"type": "img", "op": "compress", "file": m.group(1).strip(), "q": int(m.group(2) or 60)}, None
    m = re.match(r"^(?:thumbnail|thumb)(?:\s+of)?\s+(.+?)(?:\s+(\d+))?$", t)
    if m:
        return {"type": "img", "op": "thumb", "file": m.group(1).strip(), "s": int(m.group(2) or 256)}, None
    m = re.match(r"^meme\s+(\S+)\s+\"([^\"]+)\"\s+\"([^\"]+)\"$", message.strip())
    if m:
        return {"type": "img", "op": "meme", "file": m.group(1).strip(), "top": m.group(2), "bottom": m.group(3)}, None

    return None, None

def payment_parse(message: str):
    """Extract buy/order/pay item for the approval card. None if not a purchase."""
    t = message.strip().lower()
    m = re.match(r"^(?:buy|order|pay for|purchase)\s+(.+)$", t)
    if m:
        return {"kind": "payment", "item": m.group(1).strip()}
    if "payment" in t:
        return {"kind": "payment", "item": message.strip()}
    return None

def _loop_due(title: str):
    """Pull 'tomorrow 5pm' / 'in 2 hours' out of a loop title. Returns (clean_title, due_ts)."""
    import time as _t
    import datetime as _dt
    due, clean = 0, title
    m = re.search(r"\bin (\d+)\s*(hour|minute)s?\b", title)
    if m:
        n = int(m.group(1)) * (3600 if m.group(2).startswith("hour") else 60)
        due = _t.time() + n
        clean = (title[:m.start()] + title[m.end():]).strip()
    else:
        m = re.search(r"\b(tomorrow|today)(?:\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\b", title)
        if m:
            d = _dt.date.today() + (_dt.timedelta(days=1) if m.group(1) == "tomorrow" else _dt.timedelta())
            hh, mm = int(m.group(2) or 9), int(m.group(3) or 0)
            if (m.group(4) or "") == "pm" and hh < 12:
                hh += 12
            due = _dt.datetime(d.year, d.month, d.day, hh, mm).timestamp()
            clean = (title[:m.start()] + title[m.end():]).strip()
    return clean, due

def execute(action: dict, device: str = "unknown"):
    """Run it NOW on this PC. Returns reply string."""
    try:
        from app.system_tools import sanitize_reply
    except ImportError:
        from system_tools import sanitize_reply
    at = action["type"]
    if at == "loop_add":
        try:
            from app.loops import add as _ladd
        except ImportError:
            from loops import add as _ladd
        title, due = _loop_due(action.get("title", ""))
        tl = title.lower()
        if any(w in tl for w in ("buy", "order", "pay", "shop")):
            kind = "shopping"
        elif any(w in tl for w in ("trip", "travel", "flight", "hotel")):
            kind = "trip"
        elif "email" in tl or "mail" in tl:
            kind = "email"
        elif any(w in tl for w in ("meeting", "appointment", "dentist", "calendar")):
            kind = "cal"
        elif any(w in tl for w in ("outfit", "wear", "dress")):
            kind = "wardrobe"
        elif any(w in tl for w in ("reply", "call back", "message")):
            kind = "reply"
        elif "call" in tl:
            kind = "call"
        elif "save" in tl:
            kind = "save"
        else:
            kind = "promise"
        r = _ladd(kind, title, device, due)
        when = f" (due {__import__('datetime').datetime.fromtimestamp(due).strftime('%a %I:%M%p')})" if due else ""
        return f"Loop #{r['id']} open: {title}{when}."
    if at == "loop_done":
        try:
            from app.loops import close_by_title
        except ImportError:
            from loops import close_by_title
        r = close_by_title(action.get("text", ""))
        if r:
            return f"Closed loop #{r['id']} ✓"
        return "No open loop matches that."
    if at == "search_save_images":
        try:
            from app.system_tools import save_images
        except ImportError:
            from system_tools import save_images
        open_url(action["url"])  # show the search too
        r = save_images(action["query"], action.get("count", 1), action.get("dest", "desktop"))
        if r["ok"]:
            return f"Opened Google Images and saved {len(r['saved'])} image(s) on {action.get('dest', 'desktop')}: {r['saved'][0]}"
        return f"Opened Google Images, but download failed: {r.get('error')}"
    if at == "youtube_play":
        open_url(action["url"])  # Chrome opens instantly; extension auto-clicks play
        return f"Opening YouTube and playing “{action['query']}” — extension takes it from here."
    if at == "shop_browse":
        open_url(action["url"])
        b = f" under ₹{action['budget']}" if action.get("budget") else ""
        return f"Showing {action['item']}{b} on Flipkart — approve on the popup before paying anything."
    if at == "track":
        try:
            from app.goals import create
            from app.make import write_file
        except ImportError:
            from goals import create
            from make import write_file
        txt = action["text"]
        g = create(f"Track: {txt}", "", "checklist")
        fp = write_file(f"track-{g['id']}.md",
                        f"# Tracking: {txt}\n\n- [ ] Defined with Osok-AI\n- [ ] Weekly check (goals loop)\n- [ ] Done — resolve with evidence\n")
        return f"Tracking “{txt}” (goal #{g['id']}). Checklist: {fp}."
    if at == "trip_plan":
        try:
            from app.trip import plan_trip
        except ImportError:
            from trip import plan_trip
        return plan_trip(action["origin"], action["dest"], action.get("days", 3))
    if at in ("outfit_plan", "outfit_occasion", "outfit_pack", "outfit_wore", "outfit_laundry", "outfit_add"):
        try:
            from app import wardrobe as _w
        except ImportError:
            import wardrobe as _w
        if at == "outfit_plan":
            return _w.plan_week()["reply"]
        if at == "outfit_occasion":
            day = (action.get("day") or "").lower()
            iso = ""
            if day in ("today", "tomorrow"):
                import datetime as _dt
                iso = (_dt.date.today() + _dt.timedelta(days=1 if day == "tomorrow" else 0)).isoformat()
            return _w.plan_occasion(action.get("occasion", ""), iso)["reply"]
        if at == "outfit_pack":
            r = _w.pack_trip(action.get("days", 2), action.get("dest", ""))
            return r["reply"]
        if at == "outfit_wore":
            want = action.get("item", "").lower()
            hits = [i for i in _w.list_items() if want in (f"{i['color']} {i['category']}".lower()) or want in i["category"].lower()]
            if not hits:
                return f"No '{action.get('item')}' in the wardrobe — add it first ('add … to wardrobe')."
            _w.mark_worn(hits[0]["id"])
            return f"Logged: wore {hits[0]['color']} {hits[0]['category']} ✓ ({hits[0]['wears'] + 1}x total)"
        if at == "outfit_laundry":
            _w.laundry_done()
            return "Laundry done — full wardrobe fresh again. 🧺"
        if at == "outfit_add":
            desc = action.get("desc", "")
            words = desc.split()
            colors = {"white", "black", "blue", "red", "green", "yellow", "pink", "grey", "gray",
                      "brown", "beige", "navy", "maroon", "purple", "orange", "teal", "olive", "cream"}
            color = words[0] if words and words[0] in colors else ""
            category = " ".join(words[1:] if color else words) or desc
            r = _w.add_item(category, color)
            return f"Added: {color} {category} (#{r['id']}). Tell me its season/formality any time."
    if at in ("bill_quick", "bill_settle_up", "bill_repeat", "bill_house"):
        try:
            from app import bills as _b
        except ImportError:
            import bills as _b
        def _grp(name):
            g = _b.find_group(name) if name else None
            if not g:
                allg = _b.list_groups()
                if not allg:
                    return None, "No bill groups yet — create one on the Bill screen first."
                if len(allg) == 1:
                    return allg[0], ""
                return None, f"Which group? {', '.join(g['name'] for g in allg)}"
            return g, ""
        if at == "bill_quick":
            g, err = _grp(action.get("group", ""))
            if not g:
                return err
            r = _b.add_expense(g["id"], action.get("title", "Split"), float(action.get("amount", 0) or 0), "Me", {})
            if not r.get("ok"):
                return f"Split failed: {r.get('error')}"
            return f"Split ₹{action['amount']} for “{action.get('title')}” across {g['name']} ✓"
        if at == "bill_settle_up":
            g, err = _grp(action.get("group", ""))
            if not g:
                return err
            return _b.settle_up(g["id"])["reply"]
        if at == "bill_repeat":
            if action.get("freq") != "monthly":
                return "I do monthly repeats for now — say 'repeat <what> <amount> monthly in <group>'."
            g, err = _grp(action.get("group", ""))
            if not g:
                return err
            _b.add_recurring(g["id"], action.get("title", ""), float(action.get("amount", 0) or 0),
                             action.get("paid_by", "Me").title(), {}, 1)
            return f"Monthly repeat set: {action.get('title')} ₹{action['amount']} in {g['name']} ✓"
        if at == "bill_house":
            g, err = _grp(action.get("group", ""))
            if not g:
                return err
            return _b.house_ledger(g["id"])["reply"]
    if at in ("social_post", "social_status"):
        try:
            from app import social as _s
        except ImportError:
            import social as _s
        if at == "social_status":
            rows = _s.status()[:5]
            if not rows:
                return "No posts yet — say 'post <text> on <x|linkedin|mock>'."
            return "Latest posts:\n" + "\n".join(
                f"• #{r['id']} {r['platform']}: {(r['text'] or '')[:60]} — {r['status']}" for r in rows)
        if at == "social_post":
            plat, text = action.get("platform", ""), action.get("text", "")
            d = _s.draft(plat, text)
            if not d.get("ok"):
                return f"Draft failed: {d.get('error')}"
            try:
                from app.policy.dispatch import request as _gate
            except ImportError:
                from policy.dispatch import request as _gate
            g = _gate("social_publish", {"platform": plat, "text": text}, "chat")
            if g.get("waiting"):
                return (f"Drafted for {plat} (#{d['id']}). Publishing needs approval "
                        f"#{g['approval_id']} — approve on mobile/Command Port and it posts exactly this, once.")
            return f"Drafted for {plat} (#{d['id']}). Gate says: {g.get('error', 'blocked')}."
    if at in ("telegram_send", "github_brief", "github_repos", "cal_free", "cal_invite",
                "pay_collect", "wa_send", "yt_latest"):
        if at == "telegram_send":
            try:
                from app.policy.dispatch import request as _gate
            except ImportError:
                from policy.dispatch import request as _gate
            g = _gate("telegram_send", {"chat_id": action.get("chat_id", ""),
                                        "text": action.get("text", "")}, "chat")
            if g.get("waiting"):
                return (f"Telegram message staged. Send needs approval #{g['approval_id']} — "
                        f"approve and it sends exactly this, once.")
            return f"Telegram gate says: {g.get('error', 'blocked')}."
        if at == "github_brief":
            try:
                from app import github as _gh
            except ImportError:
                import github as _gh
            r = _gh.repo_brief(action.get("repo", ""))
            return r.get("reply", f"GitHub failed: {r.get('error')}")
        if at == "github_repos":
            try:
                from app import github as _gh
            except ImportError:
                import github as _gh
            r = _gh.repos()
            if not r.get("ok"):
                return f"GitHub: {r.get('error')}"
            return "Your repos:\n" + "\n".join(
                f"• {x['full']} ★{x['stars']} ({x['open_issues']} open)" for x in r["repos"][:8])
        if at == "cal_free":
            try:
                from app import calendar as _cal
            except ImportError:
                import calendar as _cal
            import datetime as _dt
            day = action.get("day", "")
            if day in ("today", "tomorrow"):
                day = (_dt.date.today() + _dt.timedelta(days=1 if day == "tomorrow" else 0)).isoformat()
            r = _cal.free_slots(day, action.get("mins", 60))
            if not r.get("ok"):
                return f"Free slots: {r.get('error')}"
            if not r["free"]:
                return f"No {action.get('mins', 60)}-min window on {r['day']}."
            return f"Free on {r['day']}: " + ", ".join(f"{s['from']}–{s['to']}" for s in r["free"][:4])
        if at == "cal_invite":
            try:
                from app import calendar as _cal
            except ImportError:
                import calendar as _cal
            r = _cal.invite(action.get("title", ""), action.get("day", ""),
                            action.get("time", ""), action.get("attendees", ""))
            if not r.get("ok"):
                return f"Invite blocked: {r.get('error')}"
            inv = f" + {len(r['invites_drafted'])} invite draft(s)" if r["invites_drafted"] else ""
            return f"Event #{r['event_id']} {r['when']}{inv} — sends stay approval-gated."
        if at == "pay_collect":
            try:
                from app import razorpay as _rz
            except ImportError:
                import razorpay as _rz
            me = ""
            try:
                from app import profile as _prof
            except ImportError:
                import profile as _prof
            try:
                me = (_prof.get_profile() or {}).get("upi_id", "")
            except Exception:
                pass
            r = _rz.collect_link(action.get("amount", 0), me or action.get("upi", ""),
                                 action.get("note", ""))
            if not r.get("ok"):
                return (f"Collect: {r.get('error')}. Set your UPI id first "
                        f"('my UPI id is name@bank' or pass a UPI id).")
            return f"Collect ₹{action['amount']}: {r['upi']}"
        if at == "wa_send":
            try:
                from app.policy.dispatch import request as _gate
            except ImportError:
                from policy.dispatch import request as _gate
            g = _gate("whatsapp_send", {"to": action.get("to", ""), "text": action.get("text", "")}, "chat")
            if g.get("waiting"):
                return (f"WhatsApp to {action.get('to')} staged. Send needs approval "
                        f"#{g['approval_id']} — approve and it sends exactly this, once.")
            return f"WhatsApp gate says: {g.get('error', 'blocked')}."
        if at == "yt_latest":
            try:
                from app import youtube as _yt
            except ImportError:
                import youtube as _yt
            r = _yt.latest_videos(action.get("channel", ""), 8)
            if not r.get("ok"):
                return f"YouTube: {r.get('error')}"
            if not r["videos"]:
                return "No recent videos found on that channel."
            return "Latest:\n" + "\n".join(
                f"• {v['title'][:70]} ({v['published']}) {v['url']}" for v in r["videos"][:5])
    if at == "img":
        try:
            from app import img as _img
        except ImportError:
            import img as _img
        try:
            op = action["op"]
            if op == "resize":
                fp = _img.img_resize(action["file"], action["w"], action.get("h", 0))
            elif op == "convert":
                fp = _img.img_convert(action["file"], action.get("fmt", "png"))
            elif op == "compress":
                fp = _img.img_compress(action["file"], action.get("q", 60))
            elif op == "thumb":
                fp = _img.img_thumbnail(action["file"], action.get("s", 256))
            else:
                fp = _img.img_caption(action["file"], action.get("top", ""), action.get("bottom", ""))
            return f"Done: {fp} (see Files tab)"
        except Exception as e:
            return f"Image failed: {e}"
    if at == "img_gen":
        try:
            from app import img as _img2
        except ImportError:
            import img as _img2
        r = _img2.img_generate(action.get("prompt", ""))
        if isinstance(r, dict) and r.get("ok"):
            return f"Generated: {r['saved']} (see Files tab)"
        return f"Generation failed: {(r.get('error') if isinstance(r, dict) else r)}"
    if at == "open_url":
        r = open_url(action["url"])
        return f"Opened {r.get('opened', action['url'])}." if r["ok"] else f"Could not open: {r.get('error')}"
    if at == "open_app":
        r = open_app(action["app"])
        return f"Opened {r['opened']}." if r["ok"] else f"Could not open {action['app']}: {r.get('error')}"
    return "done."
