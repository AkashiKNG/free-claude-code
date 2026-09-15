# Imagem do free-claude-code para rodar em container (Perez OS): servidor fcc-server + voz.
#  - extra "voice": transcrição pelo NVIDIA NIM (precisa de NVIDIA_NIM_API_KEY, WHISPER_DEVICE=nvidia_nim)
#  - extra "voice_local": Whisper local na CPU (WHISPER_DEVICE=cpu); torch para CPU, sem CUDA
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: o librosa decodifica as notas de voz (OGG/Opus do Telegram e do Discord).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 1000 appuser \
 && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin appuser

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.14 UV_CACHE_DIR=/tmp/uv-cache \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app
RUN chown appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser . .

# Projeto instalado (cria o comando fcc-server) + extra de voz do NVIDIA NIM, nas versões do uv.lock.
RUN uv sync --frozen --no-dev --extra voice \
 && rm -rf /tmp/uv-cache

# Whisper local: as dependências do extra "voice_local", com o torch de CPU.
RUN uv pip install --python /app/.venv/bin/python --torch-backend cpu \
      "torch>=2.13.0" "transformers>=5.15.0" "accelerate>=1.14.0" "librosa>=1.0.0" \
 && rm -rf /tmp/uv-cache

ENV PATH="/app/.venv/bin:$PATH"

# Modelo Whisper "base" (padrão de WHISPER_MODEL) já na imagem: a primeira nota de voz não baixa nada.
RUN python -c "from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor; AutoProcessor.from_pretrained('openai/whisper-base'); AutoModelForSpeechSeq2Seq.from_pretrained('openai/whisper-base')"

ENV HOST=0.0.0.0 PORT=8000 FCC_OPEN_BROWSER=false
EXPOSE 8000
CMD ["fcc-server"]
