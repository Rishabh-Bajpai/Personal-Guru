#!/bin/bash

# Default to false if not set
USE_CUDA=${USE_CUDA:-false}

echo "Starting Coqui TTS with USE_CUDA=$USE_CUDA"

python3 TTS/server/server.py \
    --model_name tts_models/en/vctk/vits \
    --use_cuda $USE_CUDA
