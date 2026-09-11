"""
Smoke test for the goal/supervisor/judge wiring against roam.py's actual
FastAPI app - no browser, no connectome, no live network. Everything that
would need a running fly for real (the mushroom body, page content, the AI
judge's model call) is mocked; the request/response contract between
goal.py, judge.py, supervisor.py and roam.py's /goal, /reward and /state
endpoints is exercised for real.
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

import roam
from judge import ai_goal
from supervisor import Supervisor


class FakeMushroomBody:
    """Stand-in for mushroom.MushroomBody - no connectome needed for this."""

    def __init__(self):
        self.events = []

    def dopamine(self, valence, amount):
        self.events.append((valence, amount))

    def apply(self):
        pass

    def stats(self):
        return {"rewards": sum(1 for v, _ in self.events if v > 0),
                "punishments": sum(1 for v, _ in self.events if v < 0)}


class LocalSupervisor(Supervisor):
    """A Supervisor that talks to a TestClient in-process instead of over a
    real socket - same polling/goal logic, no network involved."""

    def __init__(self, client, **kw):
        super().__init__(base_url="", **kw)
        self.client = client

    def _get(self, path):
        return self.client.get(path).json()

    def _post(self, path, payload):
        r = self.client.post(path, json=payload)
        r.raise_for_status()
        return r.json()


@pytest.fixture
def fly(tmp_path, monkeypatch):
    """roam.py's real app, its state file redirected to a scratch dir and its
    mushroom body swapped for a fake one so no connectome is needed."""
    monkeypatch.setattr(roam, "OUT", tmp_path)
    roam.STATE["mb"] = FakeMushroomBody()
    roam.STATE["goal"] = None
    return TestClient(roam.app)


def set_fly_at(state_dir, url, title):
    """Write roam_state.json the way roam.py's own publish() would, so
    /state reports the fly standing on this page without a real browser."""
    (state_dir / "roam_state.json").write_text(json.dumps({
        "url": url, "visited": [{"url": url, "title": title}],
        "updated": time.time(),
    }))


def test_goal_reshapes_seeds_and_allow(fly):
    r = fly.post("/goal", json={"name": "t", "seeds": ["http://x/a"],
                                 "allow": ["x"], "deadline_s": 30})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert roam.seed_pool() == ["http://x/a"]
    assert roam.allowed_host("http://x/a") is True
    assert roam.allowed_host("https://example.com") is False       # fence still holds

    r = fly.post("/goal", json={"seeds": []})                       # empty seeds clears it
    assert r.json()["goal"] is None
    assert roam.seed_pool() == roam.SEEDS


def test_reward_reaches_mushroom_body(fly):
    r = fly.post("/reward", json={"valence": -1, "amount": 0.4})
    assert r.json()["ok"] is True
    assert roam.STATE["mb"].events == [(-1, 0.4)]


def test_reward_without_a_loaded_brain():
    roam.STATE["mb"] = None
    r = TestClient(roam.app).post("/reward", json={"valence": 1, "amount": 1})
    assert r.json() == {"ok": False, "reason": "brain not loaded yet"}


def test_ai_goal_reached_via_supervisor(fly, tmp_path, monkeypatch):
    # stub judge: no OpenRouter call, keyword match on page content we control
    monkeypatch.setenv("FLY_JUDGE_MODEL", "stub")
    monkeypatch.setattr(
        "judge.read_page",
        lambda url, limit=2500: {"url": url, "title": "Spider facts",
                                  "text": "a page about spiders and arachnids"})

    set_fly_at(tmp_path, "http://fly/spider", "Spider facts")
    goal = ai_goal("find spiders", seeds=["http://fly/spider"],
                   description="a page about spiders or arachnids", deadline_s=5)

    result = LocalSupervisor(fly, poll_s=0.02).run_goal(goal)

    assert result.outcome == "reached"
    assert result.obs["url"] == "http://fly/spider"
    # one on_progress reward plus the fixed reward run_goal() gives on success
    assert roam.STATE["mb"].events == [(1.0, 1.0), (1.0, 1.0)]


def test_ai_goal_expires_on_an_irrelevant_page(fly, tmp_path, monkeypatch):
    monkeypatch.setenv("FLY_JUDGE_MODEL", "stub")
    monkeypatch.setattr(
        "judge.read_page",
        lambda url, limit=2500: {"url": url, "title": "Lorem ipsum",
                                  "text": "lorem ipsum dolor sit amet"})

    set_fly_at(tmp_path, "http://fly/boring", "Lorem ipsum")
    goal = ai_goal("find spiders", seeds=["http://fly/boring"],
                   description="a page about spiders or arachnids", deadline_s=0.1)

    result = LocalSupervisor(fly, poll_s=0.02).run_goal(goal)

    assert result.outcome == "expired"
    # the fixed punishment run_goal() gives on a timeout, nothing else
    assert roam.STATE["mb"].events == [(-1.0, 0.4)]
