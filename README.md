# openbrain

A real fruit fly brain, simulated neuron by neuron: 165,122 neurons and
10,228,000 signed synaptic connections, every one of them measured from an
actual male *Drosophila melanogaster* by electron microscopy, not invented,
not sampled from a distribution, not a neural network "inspired by" a brain.

This repository is a fork of the brain-simulation core of
[fruitflydev/flycoinrh](https://github.com/fruitflydev/flycoinrh), with the
Robinhood Chain / launchpad integration, the wallet, and the social-posting
"voice" module removed. What is left is the connectome, the spiking
simulation, the vision-to-motor closed loop, and the learning circuit, ready
to be pointed at something other than a token launch.

## What is in here

| file | what it does |
|---|---|
| `build_graph.py` | turns the raw connectome tables into `build/graph.npz` |
| `flysim.py` | `FlyBrain`, a leaky integrate-and-fire simulation over the connectome |
| `flyeye.py` | `FlyEye` (screen to 892 retinotopic hex columns) and `FlyPilot` (closed loop: image in, cursor out) |
| `mushroom.py` | `MushroomBody`, the dopamine-gated learning rule at the Kenyon cell to MBON synapse |
| `roam.py` | a working example: the brain drives a real, sandboxed browser with no destination and no wallet |
| `web/roam.html` | the local UI for `roam.py` |
| `envcfg.py` | reads `.env`, nothing chain-specific |

Model follows Shiu et al. 2024 (Nature): every neuron is a LIF unit with
identical passive parameters, a presynaptic spike injects a fixed voltage
scaled by synapse count into each target, and excitation/inhibition follows
predicted neurotransmitter rather than being fitted. Wiring is fixed anatomy;
per-cell-type gains are the only free parameter.

## Running it

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Fetch the connectome (CC-BY, no account or key needed) into `data/`:

```
https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/
  body-annotations-male-cns-v1.0-minconf-0.5.feather      14 MB
  body-neurotransmitters-male-cns-v1.0.feather            42 MB
  connectome-weights-male-cns-v1.0-minconf-0.5.feather   1.1 GB
```

```bash
py build_graph.py             # -> build/graph.npz, 165,122 neurons
cp .env.example .env          # then set FLY_ALLOW_BROWSER=1
py roam.py                    # http://localhost:4660
```

`roam.py` gives the brain a sandboxed browser and no instructions: a page is
screenshotted, sampled through the retina, and the descending neurons decide
where the cursor goes. It has no wallet, no keyboard, a domain allowlist, and
every click is checked before it lands (see the rails documented at the top
of `roam.py`). It is meant as a working example, not the point of this fork.

## Using the brain for something else

`FlyBrain.run()` is a generic interface: give it a drive (which neurons get
external input, at what rate) and a set of populations to record, and it
returns spike rates.

```python
from flysim import FlyBrain
fb = FlyBrain()

target = fb.where(type_re=r"^DNa02$")     # any population, by type/annotation
result = fb.run(drive={sensor_neurons: rates}, steps=100, record={"out": target})
```

`FlyEye`/`FlyPilot` are only "image in, cursor out"; the image does not have
to come from a real web page, and the output does not have to drive a mouse.
`MushroomBody` is a generic reward/punishment learning circuit: call
`observe(fired)` every step, `dopamine(+1)` or `dopamine(-1)` on your own
success/failure signal, `forget()` for slow decay, and `apply()` to write the
learned gains back into the simulation.

## Hosting it

```bash
docker build -t openbrain .
docker run -p 4660:4660 openbrain
```

The container has no wallet and no external keys, and never signs anything.

## License

The code in this repository is MIT, see `LICENSE`. The connectome dataset
itself is not ours to license: it is released CC-BY 4.0 by HHMI Janelia
FlyEM, the Cambridge Connectomics Group and Google Research, and stays under
CC-BY wherever it goes; see `NOTICE`. Simulation approach after Shiu et al.
2024 and Lappalainen et al. 2024.
