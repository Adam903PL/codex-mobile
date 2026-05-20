from django.urls import path

from .views import (
    ApprovalDecisionView,
    ApprovalRejectView,
    ApprovalRequestListCreateView,
    CodexActionCreateView,
    CodexCommandCatalogView,
    CliFinishApprovalView,
    CliNextApprovalView,
)

urlpatterns = [
    path("codex/command-catalog/", CodexCommandCatalogView.as_view(), name="codex-command-catalog"),
    path("codex/actions/", CodexActionCreateView.as_view(), name="codex-action-create"),
    path("approvals/", ApprovalRequestListCreateView.as_view(), name="approval-list-create"),
    path("approvals/<uuid:pk>/approve/", ApprovalDecisionView.as_view(), name="approval-approve"),
    path("approvals/<uuid:pk>/reject/", ApprovalRejectView.as_view(), name="approval-reject"),
    path("cli/approvals/next/", CliNextApprovalView.as_view(), name="cli-next-approval"),
    path("cli/approvals/<uuid:pk>/finish/", CliFinishApprovalView.as_view(), name="cli-finish-approval"),
    path("cli/actions/next/", CliNextApprovalView.as_view(), name="cli-next-action"),
    path("cli/actions/<uuid:pk>/finish/", CliFinishApprovalView.as_view(), name="cli-finish-action"),
]
