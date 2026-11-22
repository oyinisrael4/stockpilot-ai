from django.test import override_settings
from rest_framework.test import APITestCase
from .models import Business, Membership, User


@override_settings(ALLOW_REGISTRATION=True)
class RegistrationTests(APITestCase):
    def payload(self, **changes):
        return {"username": "private-owner", "email": "owner@example.invalid", "business_name": "Private Store",
                "password": "River!Garden5928", "confirm_password": "River!Garden5928", **changes}

    def test_confirmation_required_and_no_partial_records(self):
        for change in ({"confirm_password": "different"}, {"confirm_password": ""}, {"password": "12345678", "confirm_password": "12345678"}):
            self.assertEqual(self.client.post('/api/v1/auth/register/', self.payload(**change), format='json').status_code, 400)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Business.objects.count(), 0)

    def test_new_owner_has_only_independent_workspace(self):
        demo = Business.objects.create(name='Juniper Market Supply · Demo')
        result = self.client.post('/api/v1/auth/register/', self.payload(), format='json')
        self.assertEqual(result.status_code, 201, result.data)
        membership = Membership.objects.get(user__username='private-owner')
        self.assertNotEqual(membership.business_id, demo.pk)
        self.assertEqual(membership.role, 'owner')
        workspaces = self.client.get('/api/v1/businesses/').data
        self.assertEqual([b['id'] for b in workspaces], [membership.business_id])
        self.assertEqual(self.client.get(f'/api/v1/businesses/{demo.pk}/products/').status_code, 404)
