from django.urls import path

from . import views

app_name = 'learning'

urlpatterns = [
    path('learn/', views.dashboard, name='dashboard'),
    path('learn/certificates/', views.certificates, name='certificates'),
    path('learn/<slug:slug>/', views.resume, name='resume'),
    path('learn/<slug:slug>/lesson/<int:lesson_id>/', views.lesson_view, name='lesson'),
    path('learn/<slug:slug>/lesson/<int:lesson_id>/complete/', views.complete_lesson, name='complete_lesson'),
    path('media-protected/lesson/<int:lesson_id>/video/', views.lesson_video, name='lesson_video'),
    path('media-protected/resource/<int:resource_id>/', views.resource_download, name='resource'),
    path('certificates/<str:number>/download/', views.certificate_pdf, name='certificate_pdf'),
    path('verify/', views.verify_certificate, name='verify'),
    path('verify/<str:number>/', views.verify_certificate, name='verify_certificate'),
]
