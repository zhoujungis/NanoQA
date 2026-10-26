"""测试计划 API 路由（前缀 /api/v1/）。"""
from django.urls import path

from apps.testplans import views

urlpatterns = [
    path("projects/<int:project_id>/testplans/", views.ProjectTestPlanListCreateView.as_view()),
    path("testplans/<int:plan_id>/cases/", views.TestPlanCaseListCreateView.as_view()),
    path("testplans/<int:plan_id>/cases/<int:case_id>/", views.TestPlanCaseDetailView.as_view()),
    path("testplans/<int:plan_id>/start/", views.TestPlanStartView.as_view()),
    path("testplans/<int:plan_id>/", views.TestPlanDetailView.as_view()),
]
