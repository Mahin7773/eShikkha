from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('report/<str:target_type>/<int:pk>/', views.report, name='report'),
    path('announcements/<int:pk>/dismiss/', views.dismiss_announcement, name='dismiss_announcement'),
]
