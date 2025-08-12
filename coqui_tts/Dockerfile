FROM ghcr.io/coqui-ai/tts
EXPOSE 5002
ENTRYPOINT ["python3", "TTS/server/server.py", "--model_name", "tts_models/en/vctk/vits", "--use_cuda", "true"]
