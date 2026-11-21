import io
import os
import wave
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from rest_framework.test import APITestCase

from .assistant_voice import MAX_BYTES
from .models import AssistantConversation, AssistantExchange, AssistantProposal, Business, Membership, Sale, User


def recording():
    data = io.BytesIO()
    with wave.open(data, "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0" * 3200)
    return data.getvalue()


class VoiceTests(APITestCase):
    def setUp(self):
        business = Business.objects.create(name="Voice test")
        self.url = f"/api/v1/businesses/{business.pk}/assistant/transcribe/"
        self.user = User.objects.create_user("voice-owner")
        Membership.objects.create(user=self.user, business=business, role="owner")
        self.client.force_authenticate(self.user)

    def post_audio(self, payload):
        return self.client.post(self.url, payload, content_type="audio/wav")

    def test_requires_membership_and_valid_bounded_audio(self):
        with patch("core.assistant_voice.transcribe") as inference:
            self.assertEqual(self.post_audio(b"bad audio").status_code, 400)
            self.assertEqual(self.post_audio(b"0" * (MAX_BYTES + 1)).status_code, 400)
            self.assertEqual(self.post_audio(recording()[:-1]).status_code, 400)
            self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 415)
            self.client.force_authenticate(User.objects.create_user("voice-outsider", "outsider@example.invalid"))
            self.assertEqual(self.post_audio(recording()).status_code, 404)
            self.client.force_authenticate(None)
            self.assertIn(self.post_audio(recording()).status_code, (401, 403))
            inference.assert_not_called()

    def test_transcription_is_read_only(self):
        with patch("core.assistant_voice.transcribe", return_value="Sell two bottles of water") as inference:
            result = self.post_audio(recording())
            self.assertEqual(result.status_code, 200, result.data)
            self.assertEqual(result.data, {"text": "Sell two bottles of water"})
            inference.assert_called_once_with(b"\0" * 3200)
        for model in (AssistantConversation, AssistantExchange, AssistantProposal, Sale):
            self.assertFalse(model.objects.exists())

    @skipUnless(os.getenv("STOCKPILOT_VOICE_WAV"), "Set STOCKPILOT_VOICE_WAV to a 16 kHz mono speech fixture.")
    def test_live_offline_model(self):
        result = self.post_audio(Path(os.environ["STOCKPILOT_VOICE_WAV"]).read_bytes())
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIn("water", result.data["text"].lower())
        self.assertFalse(AssistantExchange.objects.exists())
