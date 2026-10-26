from django.urls import path

from apps.organizations import views

urlpatterns = [
    path("organizations/", views.OrganizationListCreateView.as_view(), name="organization-list"),
    path("organizations/<int:organization_id>/", views.OrganizationDetailView.as_view(), name="organization-detail"),
    path("organizations/<int:organization_id>/members/", views.OrganizationMemberListCreateView.as_view(), name="organization-member-list"),
    path("organizations/members/<int:member_id>/", views.OrganizationMemberDetailView.as_view(), name="organization-member-detail"),
]
