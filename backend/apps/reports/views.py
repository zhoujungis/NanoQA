"""报告 API（§35/§36）：Dashboard、run 报告、历史报告列表。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.executions.models import TestRun
from apps.reports.serializers import RunReportSummarySerializer
from apps.reports.services.dashboard import build_dashboard
from apps.reports.services.run_report import build_run_report, run_summaries
from common.exceptions import NotFoundError
from common.pagination import NanoPagination
from common.permissions import HasProjectPermission, resolve_project


class ProjectDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "report.read"

    def get(self, request, project_id):
        project = resolve_project(request, self)
        return Response(build_dashboard(project))


class RunReportView(APIView):
    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "report.read"

    def get_run(self) -> TestRun:
        if not hasattr(self, "_run"):
            run = TestRun.objects.filter(pk=self.kwargs["run_id"]).select_related("test_plan").first()
            if run is None:
                raise NotFoundError("测试执行不存在")
            self._run = run
        return self._run

    def get_project(self, request):
        return self.get_run().project

    def get(self, request, run_id):
        resolve_project(request, self)
        return Response(build_run_report(self.get_run()))


class ProjectReportListView(APIView):
    """历史 run 报告列表（run 摘要 + 通过率），统一分页。"""

    permission_classes = [IsAuthenticated, HasProjectPermission]
    permission_codename = "report.read"

    def get(self, request, project_id):
        project = resolve_project(request, self)
        paginator = NanoPagination()
        page = paginator.paginate_queryset(run_summaries(project), request)
        serializer = RunReportSummarySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
