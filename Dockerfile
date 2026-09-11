# The brain, on a machine that stays on.
#
# One service: the connectome simulation, a headless Chromium it drives, and
# the local web UI/websocket that watches it. No wallet, no keys, no secrets.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLY_ALLOW_BROWSER=1 \
    FLY_HOST=0.0.0.0

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt \
 && python -m playwright install --with-deps chromium

# the connectome, derived once from Janelia's CC-BY release, and any learning
# state (build/mb_gains.npz) that should survive a redeploy
COPY build/ build/
COPY data/ data/

COPY *.py ./
COPY web/ web/

CMD ["python", "roam.py"]
