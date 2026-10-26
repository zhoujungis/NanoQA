"""测试执行 API 路由（前缀 /api/v1/）。"""
from django.urls import path

from apps.executions import views

urlpatterns = [
    path("testplans/<int:plan_id>/runs/", views.TestPlanRunListCreateView.as_view()),
    path("runs/<int:run_id>/results/bulk/", views.TestRunResultBulkView.as_view()),
    path("runs/<int:run_id>/results/", views.TestRunResultListCreateView.as_view()),
    path("runs/<int:run_id>/", views.TestRunDetailView.as_view()),
    path("results/<int:result_id>/defects/", views.TestResultDefectCreateView.as_view()),
    path("results/<int:result_id>/", views.TestResultDetailView.as_view()),
]
