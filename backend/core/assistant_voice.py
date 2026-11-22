import io
import logging
import wave
from functools import lru_cache
from threading import Lock

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import BaseParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .inference import InferenceBusy, inference_slot
from .models import Membership
from .views import TenantMixin
from . import cloud_inference

SAMPLE_RATE = 16000
MAX_FRAMES = SAMPLE_RATE * 45
MAX_BYTES = MAX_FRAMES * 2 + 44
inference_lock = Lock()
logger = logging.getLogger(__name__)


class VoiceUnavailable(APIException):
    status_code = 503
    default_detail = "Transcription is unavailable. Check the configured speech provider or return to typing."


class VoiceThrottle(UserRateThrottle):
    rate = "8/min"


def read_pcm(payload):
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, SAMPLE_RATE):
                raise ValueError
            frames = audio.getnframes()
            if not 0 < frames <= MAX_FRAMES:
                raise ValueError
            pcm = audio.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError
            return pcm
    except (wave.Error, EOFError, ValueError):
        raise ValidationError("Record up to 45 seconds of supported microphone audio.") from None


@lru_cache(maxsize=1)
def speech_model():
    from faster_whisper import WhisperModel

    folder = settings.ROOT / ".local" / "whisper-tiny.en"
    if not (folder / "tokenizer.json").is_file() or not (folder / "model.bin").is_file():
        raise VoiceUnavailable()
    return WhisperModel(str(folder), device="cpu", compute_type="int8", cpu_threads=2, local_files_only=True)


def transcribe(pcm):
    if settings.VOICE_PROVIDER == "groq":
        return cloud_inference.transcribe(pcm)
    import numpy as np

    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    segments, _ = speech_model().transcribe(samples, language="en", beam_size=2, vad_filter=True,
                                            condition_on_previous_text=False)
    return " ".join(segment.text.strip() for segment in segments).strip()[:2000]


class WaveParser(BaseParser):
    media_type = "audio/wav"

    def parse(self, stream, media_type=None, parser_context=None):
        payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValidationError("The recording exceeds the 45-second limit.")
        return {"pcm": read_pcm(payload)}


class Transcription(TenantMixin, APIView):
    write_roles = tuple(Membership.Role.values)
    throttle_classes = [VoiceThrottle]
    parser_classes = [WaveParser]

    @extend_schema(request={"audio/wav": bytes}, responses={200: dict})
    def post(self, request, business_id):
        pcm = request.data.get("pcm")
        if not pcm:
            raise ValidationError("No microphone audio was provided.")

        if not inference_lock.acquire(blocking=False):
            raise VoiceUnavailable("Transcription is busy. Retry in a moment.")
        try:
            with inference_slot():
                transcript = transcribe(pcm)
        except cloud_inference.CloudUnavailable as error:
            raise VoiceUnavailable(str(error)) from None
        except InferenceBusy:
            raise VoiceUnavailable("AI is busy. Retry after the current request finishes.") from None
        except VoiceUnavailable:
            raise
        except Exception as exc:
            # Avoid logging audio, transcript text, or request details.
            logger.warning("Local transcription failed (%s)", type(exc).__name__)
            raise VoiceUnavailable() from None
        finally:
            inference_lock.release()
        return Response({"text": transcript}, headers={"Cache-Control": "no-store"})
