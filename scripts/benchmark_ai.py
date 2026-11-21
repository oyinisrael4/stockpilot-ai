"""Measure installed local inference without recording transactions or conversations."""
import json
import os
from pathlib import Path
import sys
from time import perf_counter

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockpilot.settings")
import django
django.setup()
from django.conf import settings
from django.utils import timezone
from core.assistant_intents import provider_intent
from core.assistant_voice import read_pcm, transcribe
from core.inference import inference_slot

if settings.ASSISTANT_PROVIDER != "ollama":
    raise SystemExit("This measurement runs only the installed offline Ollama provider.")
audio = Path(sys.argv[1])
measurements = {"model": settings.ASSISTANT_MODEL, "qwen_seconds": [], "whisper_seconds": []}
for prompt in ("How much profit did I make today?", "What about last month?", "Which products should I restock?"):
    start = perf_counter()
    result = provider_intent(prompt, timezone.localdate(), "NGN",
                             {"current_draft_or_topic": {"action": "profit", "period": "today"}})
    measurements["qwen_seconds"].append({"seconds": round(perf_counter() - start, 3), "action": result["action"]})
pcm = read_pcm(audio.read_bytes())
for _ in range(3):
    start = perf_counter()
    with inference_slot():
        text = transcribe(pcm)
    measurements["whisper_seconds"].append(round(perf_counter() - start, 3))
    if "water" not in text.casefold():
        raise SystemExit("The supplied fixture did not transcribe the expected word 'water'.")
print(json.dumps(measurements, indent=2))
