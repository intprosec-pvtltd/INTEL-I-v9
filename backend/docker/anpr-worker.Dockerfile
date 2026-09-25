FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INTEL_I_PROCESS_ROLE=anpr-worker \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       software-properties-common \
       ca-certificates \
       curl \
       libgl1 \
       libglib2.0-0 \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       python3.11 \
       python3.11-dev \
       python3.11-venv \
    && python3.11 -m venv /opt/venv \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt /tmp/all-requirements.txt

RUN sed \
      -e '/^torch==/d' \
      -e '/^torchvision==/d' \
      -e '/^torchaudio==/d' \
      -e '/^ultralytics==/d' \
      -e '/^ultralytics-thop==/d' \
      -e '/^onnxruntime-gpu/d' \
      -e '/^paddlepaddle==/d' \
      -e '/^--extra-index-url/d' \
      /tmp/all-requirements.txt > /tmp/requirements.txt

RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

RUN python -m pip uninstall -y \
      torch torchvision torchaudio triton \
      paddlepaddle paddlepaddle-gpu || true

RUN python -m pip install --no-cache-dir \
      paddlepaddle-gpu==3.3.1 \
      --index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/

RUN rm -f /tmp/all-requirements.txt /tmp/requirements.txt

COPY . .

RUN python -m compileall -q .

USER 65532:65532

EXPOSE 9201

CMD ["python", "-m", "workers.anpr_ocr_worker"]
