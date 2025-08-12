#!/bin/bash

# Start the TTS server in the background
python3 TTS/server/server.py --model_name tts_models/en/vctk/vits --use_cuda true &

# Keep the container running (allows the background process to continue)
tail -f /dev/null
