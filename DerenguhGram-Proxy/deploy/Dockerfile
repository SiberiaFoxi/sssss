# Non-root, tiny image. Runs inside a 128 MB container.
FROM python:3.12-slim

WORKDIR /app
COPY derenguh_proxy ./derenguh_proxy
COPY requirements.txt ./

# Optional codecs/accelerators (comment out to stay stdlib-only):
# RUN pip install --no-cache-dir brotli uvloop

# Drop privileges.
RUN useradd --create-home --uid 10001 derenguh
USER derenguh

ENV SERVER_PORT=3183 \
    SERVER_IP=0.0.0.0 \
    DERENGUH_LOG_LEVEL=info

EXPOSE 3183
# --memory=128m is enforced by the orchestrator; the app is streaming by design.
CMD ["python3", "-m", "derenguh_proxy"]
