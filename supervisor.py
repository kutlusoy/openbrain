"""
The slow loop around the fast one.

roam.py's own loop decides twice a second what the fly does through its own
eyes; nothing in that loop knows what any of it is *for*. A Supervisor is the
thing that can know that: it polls a running fly's HTTP state every few
seconds, checks the active Goal, feeds back a dopamine signal, and moves on to
the next goal once the current one is reached, expires, or is replaced.

It runs as its own process against a fly already listening on FLY_HOST:PORT
and never touches the connectome directly - only through the /goal and
/reward endpoints roam.py exposes for exactly this. That separation is
deliberate: the reflex loop keeps running unattended even if the supervisor
(or whatever AI is driving it) crashes, is slow, or is not running at all.

  py roam.py &                  the fly, listening on :4660
  py supervisor.py               runs the example schedule at the bottom
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import requests

from goal import Goal, GoalResult


@dataclass
class Supervisor:
    base_url: str = "http://127.0.0.1:4660"
    poll_s: float = 5.0
    on_result: Optional[Callable[[GoalResult], None]] = None
    log: Callable[[str], None] = field(default=print)

    def _get(self, path):
        return requests.get(f"{self.base_url}{path}", timeout=10).json()

    def _post(self, path, payload):
        r = requests.post(f"{self.base_url}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()

    def _observe(self):
        st = self._get("/state")
        visited = st.get("visited") or []
        return {
            "url": st.get("url", ""),
            "title": (visited[-1].get("title", "") if visited else ""),
            "state": st,
        }

    # -- one goal, start to finish -------------------------------------
    def run_goal(self, goal: Goal) -> GoalResult:
        """
        Hand the fly a goal and watch it until it is reached or expires.

        Setting the goal reshapes the fly's world (seeds, allowed domains);
        it does not touch the brain. Reaching or missing it does, through
        /reward - the only channel a Goal has to actually change behaviour
        rather than just describe what would count as success.
        """
        goal.start()
        self._post("/goal", {
            "name": goal.name, "seeds": goal.seeds,
            "allow": sorted(goal.allow), "deadline_s": goal.deadline_s,
        })
        self.log(f"[supervisor] goal set: {goal.name}")

        while True:
            time.sleep(self.poll_s)
            obs = self._observe()

            if goal.on_progress:
                valence = goal.on_progress(obs)
                if valence:
                    self._post("/reward", {"valence": valence,
                                            "amount": abs(valence)})

            if goal.reached(obs):
                self._post("/reward", {"valence": 1.0, "amount": 1.0})
                result = GoalResult(goal, "reached", time.time(), obs)
                break
            if goal.expired():
                self._post("/reward", {"valence": -1.0, "amount": 0.4})
                result = GoalResult(goal, "expired", time.time(), obs)
                break

        self.log(f"[supervisor] goal {result.outcome}: {goal.name}")
        if self.on_result:
            self.on_result(result)
        return result

    # -- a day's worth of goals ------------------------------------------
    def run_schedule(self, goals: Iterable[Goal]):
        """
        The fly's day: work through goals in order.

        `goals` can be a plain list (a fixed plan) or a generator that keeps
        producing the next goal from what the previous ones turned up - that
        generator is where an AI planner belongs, deciding what to look into
        next from the results this loop hands it.
        """
        results = []
        for goal in goals:
            results.append(self.run_goal(goal))
        return results


if __name__ == "__main__":
    from goal import keyword_goal

    sup = Supervisor()
    schedule = [
        keyword_goal("find something about spiders",
                     seeds=["https://en.wikipedia.org/wiki/Special:Random"],
                     keywords=["spider", "arachnid"], deadline_s=300),
        keyword_goal("find something about volcanoes",
                     seeds=["https://en.wikipedia.org/wiki/Special:Random"],
                     keywords=["volcano", "eruption", "magma"], deadline_s=300),
    ]
    for result in sup.run_schedule(schedule):
        print(f"{result.goal.name}: {result.outcome} at {result.obs['url']}")
