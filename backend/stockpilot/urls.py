from django.urls import include, path, re_path
from core.frontend import frontend
from drf_spectacular.views import SpectacularAPIView
from rest_framework.routers import SimpleRouter

from core import assistant_views, assistant_voice, finance_views, insight_views, views

tenant = "businesses/<int:business_id>/"
router = SimpleRouter()
router.register("categories", views.Categories, basename="categories")
router.register("products", views.Products, basename="products")
router.register("suppliers", views.Suppliers, basename="suppliers")
router.register("receipts", views.Receipts, basename="receipts")
router.register("customers", finance_views.Customers, basename="customers")
router.register("sales", finance_views.Sales, basename="sales")
router.register("returns", finance_views.Returns, basename="returns")
router.register("expense-categories", finance_views.ExpenseCategories, basename="expense-categories")
router.register("expenses", finance_views.Expenses, basename="expenses")
router.register("assistant/conversations", assistant_views.Conversations, basename="assistant-conversations")
router.register("assistant/proposals", assistant_views.Proposals, basename="assistant-proposals")

urlpatterns = [path("api/v1/", include([
    path("live/", views.Live.as_view()),
    path("health/", views.Health.as_view()),
    path("schema/", SpectacularAPIView.as_view()),
    path("auth/session/", views.Session.as_view()),
    path("auth/register/", views.Register.as_view()),
    path("auth/login/", views.Login.as_view()),
    path("auth/demo/", views.DemoLogin.as_view()),
    path("auth/logout/", views.Logout.as_view()),
    path("auth/profile/", views.Profile.as_view()),
    path("auth/reset/", views.PasswordReset.as_view()),
    path("auth/reset/confirm/", views.PasswordResetConfirm.as_view()),
    path("businesses/", views.Businesses.as_view()),
    path(tenant + "settings/", views.Settings.as_view()),
    path(tenant + "members/", views.Members.as_view()),
    path(tenant + "members/<int:member_id>/", views.MemberDetail.as_view()),
    path(tenant + "movements/", views.Movements.as_view()),
    path(tenant + "overview/", views.Overview.as_view()),
    path(tenant + "insights/", insight_views.Insights.as_view()),
    path(tenant + "reports/", finance_views.Reports.as_view()),
    path(tenant + "reports/csv/", finance_views.ReportCsv.as_view()),
    path(tenant + "assistant/status/", assistant_views.AssistantStatus.as_view()),
    path(tenant + "assistant/transcribe/", assistant_voice.Transcription.as_view()),
    path(tenant, include(router.urls)),
])) , re_path(r"^(?!api(?:/|$))(?P<path>.*)$", frontend)]
