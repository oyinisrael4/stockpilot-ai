import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from django.db import connection
from django.test import override_settings, RequestFactory
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

from .assistant_intents import FIELDS, SCHEMA, ProviderUnavailable, provider_intent
from . import cloud_inference
from .models import AssistantProposal, Business, InferenceUsage, Membership, Product, Sale, StockMovement, User
from .test_voice import recording
from .frontend import frontend


def intent(action, **values):
    return {"action": action, **dict.fromkeys(FIELDS, ""), **values}


@override_settings(ASSISTANT_PROVIDER="groq", ASSISTANT_MODEL="openai/gpt-oss-20b", GROQ_API_KEY="fixture-key",
                   VOICE_PROVIDER="groq", CLOUD_CHAT_MINUTE_LIMIT=5, CLOUD_CHAT_DAILY_LIMIT=50)
class CloudTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Cloud fixture")
        self.user = User.objects.create_user("cloud-owner")
        self.member = Membership.objects.create(business=self.business, user=self.user, role="owner")
        self.client.force_authenticate(self.user)
        self.base = f"/api/v1/businesses/{self.business.pk}/assistant/"
        self.thread = self.client.post(self.base + "conversations/").data["id"]
        self.product = Product.objects.create(business=self.business, name="Water", sku="WATER", price=250, cost=150, stock=10)

    def send(self, text):
        response = self.client.post(self.base + f"conversations/{self.thread}/messages/",
                                    {"text": text, "request_id": str(uuid4())}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def model_result(self, action, **values):
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(intent(action, **values))}}]}

    @patch("core.cloud_inference.request_json")
    def test_strict_intent_followup_confirmation_retry_and_backend_totals(self, request):
        request.side_effect = [self.model_result("sale", entity="WATER", quantity="2"),
                               self.model_result("continue", method="cash")]
        first = self.send("Sell two waters")
        second = self.send("In cash please")
        proposal = second["proposal"]
        self.assertIsNotNone(proposal, second)
        self.assertFalse(Sale.objects.exists())
        posted = self.client.post(self.base + f"proposals/{proposal['id']}/confirm/", {"revision": proposal["revision"]}, format="json")
        self.assertEqual(posted.status_code, 200, posted.data)
        again = self.client.post(self.base + f"proposals/{proposal['id']}/confirm/", {"revision": proposal["revision"]}, format="json")
        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Sale.objects.get().total, 500)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        payload = json.loads(request.call_args_list[0].args[1])
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], SCHEMA)
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertNotIn("tools", payload)
        self.assertNotIn("store", payload)
        self.assertIn("Sell two waters", json.loads(request.call_args_list[1].args[1])["messages"][1]["content"])

    @patch("core.cloud_inference.request_json")
    def test_cancel_and_untrusted_schema_never_write(self, request):
        request.return_value = self.model_result("sale", entity="WATER", quantity="2", method="cash")
        proposal = self.send("Sell two waters in cash")["proposal"]
        self.assertEqual(self.client.post(self.base + f"proposals/{proposal['id']}/cancel/", {"revision": proposal["revision"]}, format="json").status_code, 200)
        request.return_value = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({**intent("sale"), "confirmed": True})}}]}
        failed = self.send("Sell something")
        self.assertEqual(failed["answer"]["mode"], "provider_unavailable")
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    @patch("core.cloud_inference.request_json")
    def test_viewer_cannot_post_cloud_sale(self, request):
        self.member.role = "viewer"; self.member.save()
        request.return_value = self.model_result("sale", entity="WATER", quantity="2", method="cash")
        result = self.client.post(self.base + f"conversations/{self.thread}/messages/",
                                  {"text": "Sell two waters in cash", "request_id": str(uuid4())}, format="json")
        self.assertEqual(result.status_code, 403)
        self.assertFalse(Sale.objects.exists())

    @override_settings(CLOUD_CHAT_MINUTE_LIMIT=1)
    @patch("core.cloud_inference.request_json")
    def test_shared_quota_stops_additional_network_calls(self, request):
        request.return_value = self.model_result("stock")
        with patch("core.cloud_inference.timezone.now", return_value=timezone.now()):
            self.send("How much water is in stock?")
            self.assertEqual(InferenceUsage.objects.count(), 2)
            response = self.send("What about tea?")
        self.assertEqual(response["answer"]["mode"], "provider_unavailable")
        self.assertIn("allowance", response["answer"]["text"])
        self.assertEqual(request.call_count, 1)

    @patch("core.cloud_inference.build_opener")
    def test_provider_429_is_safe_without_retry_or_paid_fallback(self, opener):
        opener.return_value.open.side_effect = HTTPError("https://api.groq.com", 429, "private provider body", {}, None)
        result = self.send("What are my sales today?")
        self.assertIn("free quota", result["answer"]["text"])
        self.assertNotIn("private provider body", result["answer"]["text"])
        self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertFalse(AssistantProposal.objects.exists())

    @patch('core.cloud_inference.build_opener')
    def test_partial_provider_intent_only_defaults_unspecified_fields(self, opener):
        body = json.dumps({'error': {'code': 'json_validate_failed', 'failed_generation': json.dumps({'action': 'stock'})}}).encode()
        opener.return_value.open.side_effect = HTTPError('https://api.groq.com', 400, 'invalid structured result', {}, io.BytesIO(body))
        result = self.send('Check my stock')
        self.assertEqual(result['answer']['mode'], 'provider')
        self.assertIsNone(result['proposal'])
        self.assertFalse(Sale.objects.exists())

    @patch('core.cloud_inference.build_opener')
    def test_partial_provider_intent_cannot_add_unrecognized_fields(self, opener):
        body = json.dumps({'error': {'code': 'json_validate_failed', 'failed_generation': json.dumps({'action': 'stock', 'sql': 'untrusted'})}}).encode()
        opener.return_value.open.side_effect = HTTPError('https://api.groq.com', 400, 'invalid structured result', {}, io.BytesIO(body))
        result = self.send('Check my stock')
        self.assertEqual(result['answer']['mode'], 'provider_unavailable')
        self.assertFalse(Sale.objects.exists())

    @patch("core.cloud_inference.request_json")
    def test_cloud_speech_preserves_pcm_and_does_not_record_transactions(self, request):
        request.return_value = {"text": "Sell two waters"}
        result = self.client.post(self.base + "transcribe/", recording(), content_type="audio/wav")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data, {"text": "Sell two waters"})
        path, data, content_type = request.call_args.args
        self.assertEqual(path, "audio/transcriptions")
        self.assertIn(b"RIFF", data)
        self.assertIn(b"whisper-large-v3-turbo", data)
        self.assertIn("multipart/form-data", content_type)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(AssistantProposal.objects.exists())
        self.assertEqual(InferenceUsage.objects.filter(key__startswith="groq:audio:").count(), 2)

    @patch("core.cloud_inference.request_json")
    def test_invalid_audio_is_rejected_before_cloud_and_quota(self, request):
        self.assertEqual(self.client.post(self.base + "transcribe/", b"not audio", content_type="audio/wav").status_code, 400)
        request.assert_not_called()
        self.assertFalse(InferenceUsage.objects.exists())

    def test_liveness_never_uses_database(self):
        with self.assertNumQueries(0):
            self.assertEqual(APIClient().get("/api/v1/live/").status_code, 200)

    def test_spa_static_is_same_origin_and_never_serves_private_paths(self):
        with TemporaryDirectory() as directory, override_settings(SERVE_FRONTEND=True, FRONTEND_DIST=Path(directory)):
            (Path(directory) / "index.html").write_text("<main>Fixture SPA</main>")
            response = frontend(RequestFactory().get("/pos"), "pos")
            self.assertEqual(response.status_code, 200)
            self.assertIn("connect-src 'self'", response["Content-Security-Policy"])
            self.assertEqual(response["Cache-Control"], "no-store")
            response.file_to_stream.close()
            for path in ("/.env", "/backend/settings.py", "/api/v1/missing/", "/assets/../../.env"):
                self.assertEqual(self.client.get(path).status_code, 404)

    @override_settings(PASSWORD_RESET_ENABLED=False)
    def test_disabled_email_recovery_gives_explicit_unavailability(self):
        response = self.client.post("/api/v1/auth/reset/", {"email": "unknown@example.invalid"}, format="json")
        self.assertEqual(response.status_code, 503)

    @patch.dict(os.environ, {"STOCKPILOT_PUBLIC_DEMO": "1"})
    def test_demo_entry_cannot_activate_on_a_genuine_database(self):
        self.assertNotEqual(connection.settings_dict["NAME"], "stockpilot_demo")
        response = APIClient().post("/api/v1/auth/demo/")
        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"STOCKPILOT_PUBLIC_DEMO": "1"})
    def test_shared_demo_identity_cannot_be_renamed(self):
        self.user.username = "demo-visitor"; self.user.save()
        self.assertEqual(self.client.patch("/api/v1/auth/profile/", {"username": "renamed"}, format="json").status_code, 403)
