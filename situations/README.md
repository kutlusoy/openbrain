# Situations

This is where application scenarios for the brain get designed and
prototyped. `roam.py` at the repository root is the first one that exists -
a real connectome driving a sandboxed browser - and it is useful as a working
example, but it is not the point of this project. Read the rest of this file
before starting a new one; it explains what "the point" actually is.

## The goal

Steering a mouse cursor around a browser is not the target. The target is a
real artificial being that acts in the physical world: a real biological
neural network (the connectome, unmodified - that is the whole reason this
project exists rather than a plain neural net) as its actual nervous system,
given a real body - a camera, a microphone, a speaker, motors, whatever
sensors and actuators a given situation calls for - and an LLM/AI layer
alongside it for language, planning and judgement, the way `goal.py` /
`supervisor.py` / `judge.py` already sit alongside the connectome for the
browser case without ever touching its weights directly.

None of that is built yet outside of the browser. This file, and this
folder, is where it gets built.

## What a Situation is

`flyeye.py`'s pattern already generalizes past browsers: sensory data goes in
as drive on some set of neurons (`FlyEye.look()` turns pixels into a rate per
retina column), and the descending neurons that come out get turned into
whatever motor action the situation actually has (`FlyPilot.step()` turns DN
firing rates into cursor `dx, dy, click`). A Situation is that same pairing
for a real body instead of a browser DOM:

- **sense**: turn real sensor input (camera frame, microphone audio, any
  other sensor) into `drive = {neuron_indices: rates}` for `FlyBrain.run()`,
  the same shape `FlyEye.look()` already produces.
- **act**: turn the recorded populations' firing rates into real actuator
  commands (speaker output, motor movement) instead of a cursor.
- **observe/goal**: expose enough state (what the sensors are currently
  seeing/hearing, what the actuators just did) that `goal.py`'s `check`/
  `on_progress` and `judge.py`'s `ai_goal()` can be pointed at it exactly as
  they are pointed at `roam.py`'s `/state` today. `supervisor.py` does not
  care whether the process on the other end of `/goal` and `/reward` is
  driving a browser or a robot.

A new situation should not need to change `goal.py`, `supervisor.py` or
`judge.py` at all - if it does, that is a sign the sense/act/observe seam
needs to be generalized further, not that the situation should reach past it
into the connectome directly.

## Planned situations

| name | senses | acts | status |
|---|---|---|---|
| `browser/` | a screenshot, sampled through the retina (`flyeye.py`) | cursor move/click, page scroll | exists - see `roam.py` at the repository root |
| `webcam-mic/` | a camera frame through the retina; microphone audio through a new auditory drive channel | speaker output (through the LLM/voice layer) | idea |
| a physical body | camera, microphone, and whatever other sensors the platform has | motors, speaker | idea |

Each situation that moves past "idea" gets its own subfolder here with its
own sense/act code and its own README describing what it actually does and,
just as importantly, what it does not - in the style of the rest of this
project: measured and built is one thing, invented and asserted is another,
and the two are never presented as the same.
