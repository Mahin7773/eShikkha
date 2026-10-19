from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.course_list, name='list'),
    path('instructors/<str:username>/', views.instructor_profile, name='instructor'),
    path('<slug:slug>/', views.course_detail, name='detail'),
    path('<slug:slug>/review/', views.submit_review, name='review'),
]
