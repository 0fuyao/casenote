#!/usr/bin/env bash
# One-time setup (needs internet). After this, CaseNote runs with WiFi off.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "Downloading Bonsai 2 9B (MLX 2-bit, ~3.4 GB) ..."
.venv/bin/python -c "from huggingface_hub import snapshot_download as d; d('prism-ml/Ternary-Bonsai-2-9B-mlx-2bit', local_dir='models/bonsai2-9B-mlx')"

echo "Installing Argmax OSS CLI (WhisperKit + TTSKit) ..."
command -v whisperkit-cli >/dev/null || brew install whisperkit-cli
command -v ffmpeg >/dev/null || brew install ffmpeg

echo "Downloading Argmax models (Whisper large-v3 turbo + Qwen3-TTS) ..."
mkdir -p scratch models/argmax
whisperkit-cli tts --text "Setup complete." --output-path scratch/setup --output-format wav
whisperkit-cli transcribe --audio-path scratch/setup.wav --model large-v3-v20240930_turbo_632MB --download-model-path models/argmax
whisperkit-cli diarize --audio-path scratch/setup.wav --download-model-path models/argmax

.venv/bin/python tools/make_specimens.py
echo "Done. Turn WiFi off and run ./run.sh"
