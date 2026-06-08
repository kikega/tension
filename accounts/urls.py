from django.urls import path
from django.views.generic import TemplateView
from .views import (
    SignUpView,
    AccessRequestListView,
    ApproveAccessRequestView,
    RejectAccessRequestView,
)

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "signup/pending/",
        TemplateView.as_view(template_name="registration/signup_pending.html"),
        name="signup_pending"
    ),
    path("requests/", AccessRequestListView.as_view(), name="access_requests_list"),
    path("requests/<int:pk>/approve/", ApproveAccessRequestView.as_view(), name="approve_access_request"),
    path("requests/<int:pk>/reject/", RejectAccessRequestView.as_view(), name="reject_access_request"),
]
