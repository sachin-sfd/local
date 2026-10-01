"""Runs ONE check (GitHub Actions calls this every 5 minutes) and notifies via ntfy on any change."""
import difflib, json, os, re, requests

URLS = [
    "https://navshaktinavratri.in/",
    "https://navshaktinavratri.in/register",
]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = "state.json"
GFORM = re.compile(r"(docs\.google\.com/forms[^\s\"'<>]*|forms\.gle/[^\s\"'<>]*|goo\.gl/forms/[^\s\"'<>]*)", re.I)


def notify(title, msg, click=None):
    h = {"Title": title, "Priority": "high"}
    if click:
        h["Click"] = click
    r = requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"), headers=h, timeout=15)
    print("ntfy:", r.status_code)


def lines_of(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", html)
    out = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    return [l for l in out if l]


def snap(url):
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return {"lines": lines_of(r.text), "gforms": sorted(set(GFORM.findall(r.text))),
            "has_form": "<form" in r.text.lower()}


state = json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
for url in URLS:
    try:
        new = snap(url)
    except Exception as e:
        print("error", url, e)
        continue
    old = state.get(url)
    if old:
        msgs = []
        added = set(new["gforms"]) - set(old["gforms"])
        if added:
            msgs.append("Google Form link: " + ", ".join(added))
        if new["has_form"] != old["has_form"]:
            msgs.append("Form " + ("appeared" if new["has_form"] else "removed"))
        diff = [d for d in difflib.unified_diff(old["lines"], new["lines"], lineterm="", n=0)
                if d[:1] in "+-" and d[:3] not in ("+++", "---")]
        if diff:
            msgs.append("Text changed: " + " | ".join(diff[:6])[:350])
        if msgs:
            notify("Page changed", url + "\n" + "\n".join(msgs), click=url)
    else:
        print("baseline saved", url)
    state[url] = new

json.dump(state, open(STATE_FILE, "w"), ensure_ascii=False)
