from django.urls import path

from .views import CliProjectCreateView, CliProjectDetailView, ProjectDetailView, ProjectGitBranchActionView, ProjectListView

urlpatterns = [
    path("projects/", ProjectListView.as_view(), name="project-list"),
    path("projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/git/branch/", ProjectGitBranchActionView.as_view(), name="project-git-branch"),
    path("cli/projects/", CliProjectCreateView.as_view(), name="cli-projects"),
    path("cli/projects/<uuid:pk>/", CliProjectDetailView.as_view(), name="cli-project-detail"),
]
