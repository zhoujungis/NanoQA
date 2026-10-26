"""需求路由（挂载于 /api/v1/ 下）。"""
from django.urls import path

from apps.requirements.views import RequirementViewSet

urlpatterns = [
    path(
        "projects/<int:project_id>/requirements/",
        RequirementViewSet.as_view({"get": "list", "post": "create"}),
        name="requirement-list",
    ),
    path(
        "requirements/<int:pk>/",
        RequirementViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="requirement-detail",
    ),
    path(
        "requirements/<int:pk>/testcases/",
        RequirementViewSet.as_view({"post": "link_testcases", "delete": "unlink_testcases"}),
        name="requirement-testcases",
    ),
    path(
        "requirements/<int:pk>/testcases/<int:case_id>/",
        RequirementViewSet.as_view({"delete": "unlink_testcase"}),
        name="requirement-testcase-detail",
    ),
    path(
        "requirements/<int:pk>/coverage/",
        RequirementViewSet.as_view({"get": "coverage"}),
        name="requirement-coverage",
    ),
]
