"""NanoQA 总路由：所有业务 API 挂载在 /api/v1/。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def ping(_request):
    return JsonResponse({"code": 0, "message": "success", "data": {"service": "nanoqa", "version": "0.1"}})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/ping/", ping),
    path("api/v1/auth/", include("apps.accounts.urls_auth")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.testcases.urls")),
    path("api/v1/", include("apps.requirements.urls")),
    path("api/v1/", include("apps.testplans.urls")),
    path("api/v1/", include("apps.executions.urls")),
    path("api/v1/", include("apps.defects.urls")),
    path("api/v1/", include("apps.reports.urls")),
    path("api/v1/", include("apps.attachments.urls")),
    path("api/v1/", include("apps.ai.urls")),
    path("api/v1/", include("apps.audit.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
