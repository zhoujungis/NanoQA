"""缺陷路由（挂载于 /api/v1/ 下）。"""
from django.urls import path

from apps.defects.views import DefectViewSet

urlpatterns = [
    path(
        "projects/<int:project_id>/defects/",
        DefectViewSet.as_view({"get": "list", "post": "create"}),
        name="defect-list",
    ),
    path(
        "defects/<int:pk>/",
        DefectViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="defect-detail",
    ),
    path(
        "defects/<int:pk>/testcases/",
        DefectViewSet.as_view({"post": "link_testcases"}),
        name="defect-testcases",
    ),
    path(
        "defects/<int:pk>/testcases/<int:case_id>/",
        DefectViewSet.as_view({"delete": "unlink_testcase"}),
        name="defect-testcase-detail",
    ),
    path(
        "defects/<int:pk>/requirements/",
        DefectViewSet.as_view({"post": "link_requirements"}),
        name="defect-requirements",
    ),
    path(
        "defects/<int:pk>/requirements/<int:req_id>/",
        DefectViewSet.as_view({"delete": "unlink_requirement"}),
        name="defect-requirement-detail",
    ),
]
