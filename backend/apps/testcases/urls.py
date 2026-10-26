"""测试用例路由（§45）：挂载在 /api/v1/ 下。"""
from django.urls import path

from apps.testcases import views

urlpatterns = [
    path("projects/<int:project_id>/testcases/", views.TestCaseListCreateView.as_view(), name="testcase-list"),
    path("projects/<int:project_id>/testcases/batch/", views.TestCaseBatchView.as_view(), name="testcase-batch"),
    path("projects/<int:project_id>/export/testcases/", views.TestCaseExportView.as_view(), name="testcase-export"),
    path("projects/<int:project_id>/import/testcases/", views.TestCaseImportView.as_view(), name="testcase-import"),
    path("testcases/<int:pk>/", views.TestCaseDetailView.as_view(), name="testcase-detail"),
    path("testcases/<int:pk>/restore/", views.TestCaseRestoreView.as_view(), name="testcase-restore"),
    path("testcases/<int:pk>/duplicate/", views.TestCaseDuplicateView.as_view(), name="testcase-duplicate"),
    path("testcases/<int:pk>/move/", views.TestCaseMoveView.as_view(), name="testcase-move"),
    path("testcases/<int:pk>/versions/", views.TestCaseVersionsView.as_view(), name="testcase-versions"),
    path("testcases/<int:pk>/history/", views.TestCaseHistoryView.as_view(), name="testcase-history"),
    path("testcase-versions/<int:pk>/", views.TestCaseVersionDetailView.as_view(), name="testcase-version-detail"),
]
