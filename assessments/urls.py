from django.urls import path

from . import views

app_name = 'assessments'

urlpatterns = [
    path('<slug:slug>/quiz/<int:quiz_id>/', views.quiz_detail, name='quiz'),
    path('<slug:slug>/quiz/<int:quiz_id>/start/', views.start_quiz, name='start'),
    path('<slug:slug>/attempt/<int:attempt_id>/', views.take_quiz, name='take'),
    path('<slug:slug>/attempt/<int:attempt_id>/result/', views.attempt_result, name='result'),
]
