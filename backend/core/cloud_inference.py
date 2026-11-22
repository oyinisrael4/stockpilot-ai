"""Bounded, server-only Groq transport. No retries, provider fallback or paid tools."""
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import InferenceUsage


class CloudUnavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def reserve(kind, amount=1):
    now = timezone.now()
    if kind == "chat":
        windows = [(now.strftime("%Y-%m-%d"), settings.CLOUD_CHAT_DAILY_LIMIT),
                   (now.strftime("%Y-%m-%dT%H:%M"), settings.CLOUD_CHAT_MINUTE_LIMIT)]
    else:
        windows = [(now.strftime("%Y-%m-%d"), settings.CLOUD_AUDIO_DAILY_SECONDS),
                   (now.strftime("%Y-%m-%dT%H"), settings.CLOUD_AUDIO_HOURLY_SECONDS)]
    # Reserve before sending. Failed requests still consume the local allowance.
    with transaction.atomic():
        rows = []
        for window, limit in windows:
            record, _ = InferenceUsage.objects.get_or_create(key=f"groq:{kind}:{window}")
            record = InferenceUsage.objects.select_for_update().get(pk=record.pk)
            if record.units + amount > limit:
                raise CloudUnavailable("The shared cloud AI allowance is temporarily exhausted. Try later; manual controls remain available.")
            rows.append(record)
        for record in rows:
            record.units += amount
            record.save(update_fields=["units"])


def request_json(path, body, content_type="application/json"):
    if not settings.GROQ_API_KEY:
        raise CloudUnavailable("Cloud AI is not configured. Return to manual controls or contact the demo owner.")
    request = Request("https://api.groq.com/openai/v1/" + path, data=body,
                      headers={"Authorization": "Bearer " + settings.GROQ_API_KEY, "Content-Type": content_type,
                               "User-Agent": "StockPilotAI/1.0", "Accept": "application/json"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=35) as response:
            raw = response.read(65537)
        if len(raw) > 65536: raise ValueError()
        return json.loads(raw)
    except HTTPError as error:
        if error.code == 429:
            raise CloudUnavailable("Groq's free quota or rate limit has been reached. Wait and retry; no paid fallback is enabled.") from None
        if error.code in (400, 404):
            raise CloudUnavailable("The configured cloud model is unavailable or rejected the request. Contact the demo owner.") from None
        raise CloudUnavailable("Cloud AI is temporarily unavailable. Try later or use manual controls.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise CloudUnavailable("Cloud AI could not respond. Try later or use manual controls.") from None


def intent(payload, schema):
    if settings.ASSISTANT_MODEL not in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        raise CloudUnavailable("Select a supported Groq strict-output model in the server configuration.")
    payload.update(temperature=0, reasoning_effort="low", max_completion_tokens=1200,
                   response_format={"type": "json_schema", "json_schema": {
                       "name": "select_workspace_intent", "strict": True, "schema": schema}})
    body = json.dumps(payload).encode()
    if len(body) > 24000:
        raise CloudUnavailable("This conversation request is too large. Start a new conversation or shorten the message.")
    reserve("chat")
    result = request_json("chat/completions", body)
    choice = result["choices"][0]
    if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
        raise CloudUnavailable("Cloud AI did not return a complete intent. Try rephrasing your request.")
    return choice["message"]["content"]


def transcribe(pcm):
    import io
    import wave
    if settings.GROQ_VOICE_MODEL not in ("whisper-large-v3-turbo", "whisper-large-v3"):
        raise CloudUnavailable("The configured cloud speech model is unsupported.")
    reserve("audio", max(10, math.ceil(len(pcm) / 32000)))
    audio = io.BytesIO()
    with wave.open(audio, "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(pcm)
    boundary = "stockpilot" + uuid4().hex
    chunks = []
    for name, value in (("model", settings.GROQ_VOICE_MODEL), ("language", "en"), ("response_format", "json")):
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recording.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),
               audio.getvalue(), f'\r\n--{boundary}--\r\n'.encode()]
    result = request_json("audio/transcriptions", b"".join(chunks), "multipart/form-data; boundary=" + boundary)
    text = result.get("text")
    if not isinstance(text, str) or len(text) > 2000:
        raise CloudUnavailable("Cloud speech returned an invalid transcript. Try a shorter recording.")
    return text.strip()
