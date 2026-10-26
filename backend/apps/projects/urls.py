from django.urls import path

from apps.projects import views

urlpatterns = [
    path("projects/", views.ProjectListCreateView.as_view(), name="project-list"),
    path("projects/<int:project_id>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:project_id>/members/", views.ProjectMemberListCreateView.as_view(), name="project-member-list"),
    path("projects/members/<int:member_id>/", views.ProjectMemberDetailView.as_view(), name="project-member-detail"),
    path("projects/<int:project_id>/modules/", views.ModuleTreeCreateView.as_view(), name="project-module-list"),
    path("projects/<int:project_id>/tags/", views.TagListCreateView.as_view(), name="project-tag-list"),
    path("modules/<int:module_id>/", views.ModuleDetailView.as_view(), name="module-detail"),
    path("modules/<int:module_id>/move/", views.ModuleMoveView.as_view(), name="module-move"),
    path("tags/<int:tag_id>/", views.TagDetailView.as_view(), name="tag-detail"),
]
