"""
An AI judge for goal.py's `check`/`on_progress` seam.

`keyword_goal()` only matches text already sitting in a title or URL. This
reads the page the fly currently stands on - an independent HTTP GET, not
through the fly's own eyes; its retina is 892 hex columns of light and reads
nothing - and asks a language model whether that page counts as progress
toward a goal stated in plain language. That is the only place in this
project language is allowed to mean something: the connectome still has no
idea what "spider" means, it is only ever rewarded or not through /reward.

Same OPENROUTER_API_KEY / model convention as the rest of the project.
FLY_JUDGE_MODEL=stub runs a crude offline keyword fallback with no network
call, for testing without a key.

  py judge.py "https://en.wikipedia.org/wiki/Spider" "find a page about spiders"
"""
import html
import json
import os
import re

import requests

from envcfg import load_env
from goal import Goal

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 openbrain-judge/1.0")


def _get(key, default=None):
    v = load_env().get(key) or os.environ.get(key)
    return v if v not in (None, "") else default


def _model():
    return _get("FLY_JUDGE_MODEL", "anthropic/claude-opus-5")


def _key():
    return _get("OPENROUTER_API_KEY")


def strip_html(raw):
    raw = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def read_page(url, limit=2500):
    """A plain-text read of the page, independent of the fly's own vision."""
    out = {"url": url, "title": url, "text": ""}
    if not url.startswith(("http://", "https://")):
        return out
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA})
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
        if m:
            out["title"] = " ".join(html.unescape(m.group(1)).split())[:140]
        out["text"] = strip_html(r.text)[:limit]
    except Exception:
        pass
    return out


PROMPT = """You judge whether a page a web-roaming agent landed on counts as
progress toward a stated goal. You are given the goal in plain language and
the page's title, url and a text excerpt. Reply with JSON only, exactly:
{"reached": bool, "valence": float, "reason": str}
valence is in [-1, 1]: positive if the page is relevant/on-track, negative if
it is a dead end or clearly off-topic, 0 if you cannot tell. "reached" is
true only if the goal is clearly satisfied by this specific page, not merely
"getting warmer". Keep "reason" under 20 words."""


def parse_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def call_model(goal_desc, page):
    key = _key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    user = json.dumps({
        "goal": goal_desc,
        "page": {"url": page["url"], "title": page["title"],
                 "excerpt": page["text"][:2000]},
    }, ensure_ascii=False)
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": _model(), "temperature": 0.0, "max_tokens": 200,
              "messages": [{"role": "system", "content": PROMPT},
                           {"role": "user", "content": user}]},
        timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"openrouter {r.status_code}: {r.text[:200]}")
    text = r.json()["choices"][0]["message"]["content"]
    return parse_json(text)


def stub_verdict(goal_desc, page):
    """Offline fallback: crude keyword overlap, no network call."""
    words = {w.lower() for w in re.findall(r"[a-zA-Z]{4,}", goal_desc)}
    hay = f"{page['title']} {page['text'][:1000]}".lower()
    hits = sum(1 for w in words if w in hay)
    need = max(1, len(words) // 2)
    valence = min(1.0, hits / need)
    return {"reached": hits >= need, "valence": round(valence, 2),
            "reason": f"stub: {hits}/{len(words)} goal words present"}


def judge(goal_desc, url):
    """
    The judgement for one page: {"reached", "valence", "reason"}.

    Never raises - a judge call that fails (no key, rate limit, bad JSON
    back) should not kill the supervisor loop, so it reports "no opinion"
    (valence 0, not reached) instead.
    """
    page = read_page(url)
    if not page["text"]:
        return {"reached": False, "valence": 0.0, "reason": "page unreadable"}
    try:
        if _model().strip().lower() == "stub":
            return stub_verdict(goal_desc, page)
        return call_model(goal_desc, page)
    except Exception as exc:
        return {"reached": False, "valence": 0.0, "reason": f"judge error: {str(exc)[:120]}"}


def ai_goal(name, seeds, description, allow=(), deadline_s=600.0):
    """
    A Goal (see goal.py) whose check/on_progress call the judge above instead
    of keyword_goal's plain text match. `description` is the goal in plain
    language, handed to the model as-is.

    The judge is only called once per distinct URL the fly is standing on -
    on_progress and check both ask for "the current verdict" every poll tick,
    and re-reading the same page twice a tick would just double the cost for
    the same answer.
    """
    cache = {"url": None, "verdict": None}

    def _verdict(obs):
        url = obs.get("url") or ""
        if not url:
            return {"reached": False, "valence": 0.0, "reason": "no url"}
        if cache["url"] != url:
            cache["url"] = url
            cache["verdict"] = judge(description, url)
        return cache["verdict"]

    def check(obs):
        return bool(_verdict(obs).get("reached"))

    def on_progress(obs):
        return float(_verdict(obs).get("valence") or 0.0)

    return Goal(name=name, seeds=list(seeds), allow=set(allow),
                deadline_s=deadline_s, check=check, on_progress=on_progress)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: py judge.py <url> <goal description>")
        raise SystemExit(1)
    print(json.dumps(judge(sys.argv[2], sys.argv[1]), indent=1))
