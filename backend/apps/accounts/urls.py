from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("roles/", views.RoleListCreateView.as_view(), name="role-list"),
    path("roles/<int:role_id>/", views.RoleDetailView.as_view(), name="role-detail"),
]
