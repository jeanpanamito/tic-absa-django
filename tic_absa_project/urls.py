"""
Root URL configuration for tic_absa_project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('analytics.urls')),
]
