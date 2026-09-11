"""
Goals a supervisor can hand to a running fly.

A Goal is deliberately dumb about *how* it gets achieved. The connectome has
no language and cannot be told "find the recipe for X" - what it can do is
react to the world it is dropped into. So a Goal only shapes that world (which
pages a life starts from, which extra domains the fence opens for) and
judges, from the outside, whether wandering there counted as progress.

`check` and `on_progress` are the seam. `keyword_goal` below is the simplest
possible judge - a page counts if its title/url contains a keyword - and is a
placeholder for whatever real judgement should sit there instead: an AI
reading the page, a human, a downstream check against some other system. See
supervisor.py for how a Goal is actually run against a live fly.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Goal:
    name: str
    seeds: list                                # where a life on this goal starts
    allow: set = field(default_factory=set)    # extra domains added to the fence
    deadline_s: Optional[float] = 600.0        # None = no time limit
    check: Optional[Callable[[dict], bool]] = None       # obs -> reached?
    on_progress: Optional[Callable[[dict], Optional[float]]] = None
    # ^ obs -> a valence in [-1, 1] to reward/punish on this tick, or None/0
    #   for "no opinion yet". Runs every poll, independent of `check`.

    started_at: Optional[float] = field(default=None, init=False, repr=False)

    def start(self):
        self.started_at = time.time()

    def expired(self):
        return (self.deadline_s is not None and self.started_at is not None
                and time.time() - self.started_at > self.deadline_s)

    def reached(self, obs):
        return bool(self.check and self.check(obs))


@dataclass
class GoalResult:
    goal: Goal
    outcome: str          # "reached" | "expired" | "aborted"
    at: float
    obs: dict


def keyword_goal(name, seeds, keywords, allow=(), deadline_s=600.0):
    """A page counts as reached if its title or url contains any keyword."""
    words = [k.lower() for k in keywords]

    def check(obs):
        hay = f"{obs.get('title', '')} {obs.get('url', '')}".lower()
        return any(w in hay for w in words)

    return Goal(name=name, seeds=list(seeds), allow=set(allow),
                deadline_s=deadline_s, check=check)
