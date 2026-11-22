import json
from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import Business, Product, User, Membership, Sale
from .business_conversation import answer_question
from .assistant_intents import ProviderUnavailable


@override_settings(ASSISTANT_PROVIDER='groq', ASSISTANT_MODEL='openai/gpt-oss-20b', GROQ_API_KEY='fixture')
class ConversationTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Conversation fixture')
        self.user = User.objects.create_user('conversation-owner')
        Membership.objects.create(user=self.user, business=self.business, role='owner')
        foreign = Business.objects.create(name='Private other tenant')
        Product.objects.create(business=foreign, sku='PRIVATE', name='Confidential other product')

    @patch('core.business_conversation.generate')
    def test_open_question_uses_scoped_evidence_and_model_response(self, generate):
        generate.return_value = json.dumps({'sections': [{'kind': 'suggestion', 'text': 'Ask customers what keeps them returning before testing a new promotion.', 'sources': []}]})
        answer = answer_question(self.business, 'How could I make my shop more memorable?', {'action': 'analysis'}, [])
        self.assertIn('Ask customers', answer['text'])
        payload = json.dumps(generate.call_args.args[0])
        self.assertNotIn('Confidential other product', payload)
        self.assertFalse(Sale.objects.exists())

    @patch('core.business_conversation.generate')
    def test_invented_figures_and_uncited_claims_are_rejected(self, generate):
        for section in [
            {'kind': 'finding', 'text': 'Sales increased dramatically.', 'sources': []},
            {'kind': 'suggestion', 'text': 'Spend 987654321 on marketing.', 'sources': []},
        ]:
            generate.return_value = json.dumps({'sections': [section]})
            with self.assertRaises(ProviderUnavailable):
                answer_question(self.business, 'What next?', {'action': 'analysis'}, [])
        self.assertFalse(Sale.objects.exists())

    @override_settings(ALLOW_REGISTRATION=False)
    def test_production_registration_is_closed(self):
        result = self.client.post('/api/v1/auth/register/', {}, format='json')
        self.assertEqual(result.status_code, 403)
