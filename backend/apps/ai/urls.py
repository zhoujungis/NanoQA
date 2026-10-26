"""AI 路由（§45 AI）：/api/v1/ 前缀由 config.urls 挂载。"""
from django.urls import path

from apps.ai.views import (
    AcceptTaskView,
    AITaskDetailView,
    AITaskListView,
    AnalyzeDefectView,
    AnalyzeRequirementView,
    DetectDuplicatesView,
    ExpandCaseView,
    GenerateTestcasesView,
    RejectTaskView,
    ReviewCaseView,
)

urlpatterns = [
    path("ai/testcases/generate/", GenerateTestcasesView.as_view(), name="ai-testcase-generate"),
    path("ai/testcases/detect-duplicates/", DetectDuplicatesView.as_view(), name="ai-testcase-duplicates"),
    path("ai/testcases/<int:case_id>/review/", ReviewCaseView.as_view(), name="ai-testcase-review"),
    path("ai/testcases/<int:case_id>/expand/", ExpandCaseView.as_view(), name="ai-testcase-expand"),
    path("ai/requirements/<int:requirement_id>/analyze/", AnalyzeRequirementView.as_view(), name="ai-requirement-analyze"),
    path("ai/defects/<int:defect_id>/analyze/", AnalyzeDefectView.as_view(), name="ai-defect-analyze"),
    path("ai/tasks/", AITaskListView.as_view(), name="ai-task-list"),
    path("ai/tasks/<int:task_id>/accept/", AcceptTaskView.as_view(), name="ai-task-accept"),
    path("ai/tasks/<int:task_id>/reject/", RejectTaskView.as_view(), name="ai-task-reject"),
    path("ai/tasks/<int:task_id>/", AITaskDetailView.as_view(), name="ai-task-detail"),
]
