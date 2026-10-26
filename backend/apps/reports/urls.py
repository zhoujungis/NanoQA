"""报告路由（§45 Reports）：/api/v1/ 前缀由 config.urls 挂载。"""
from django.urls import path

from apps.reports.views import ProjectDashboardView, ProjectReportListView, RunReportView

urlpatterns = [
    path("projects/<int:project_id>/dashboard/", ProjectDashboardView.as_view(), name="project-dashboard"),
    path("projects/<int:project_id>/reports/", ProjectReportListView.as_view(), name="project-reports"),
    path("runs/<int:run_id>/report/", RunReportView.as_view(), name="run-report"),
]
