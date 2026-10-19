from django.urls import path

from . import views

app_name = 'studio'

C = 'courses/<int:pk>/'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('earnings/', views.earnings, name='earnings'),
    path('courses/new/', views.course_create, name='course_create'),
    path(C, views.course_overview, name='course'),
    path(C + 'edit/', views.course_edit, name='course_edit'),
    path(C + 'submit/', views.course_submit, name='course_submit'),
    path(C + 'archive/', views.course_archive, name='course_archive'),
    path(C + 'restore/', views.course_restore, name='course_restore'),
    path(C + 'delete/', views.course_delete, name='course_delete'),

    path(C + 'curriculum/', views.curriculum, name='curriculum'),
    path(C + 'sections/add/', views.section_create, name='section_create'),
    path(C + 'sections/<int:section_id>/edit/', views.section_edit, name='section_edit'),
    path(C + 'sections/<int:section_id>/delete/', views.section_delete, name='section_delete'),
    path(C + 'sections/<int:section_id>/move/<str:direction>/', views.section_move, name='section_move'),
    path(C + 'sections/<int:section_id>/lessons/add/', views.lesson_create, name='lesson_create'),
    path(C + 'lessons/<int:lesson_id>/', views.lesson_edit, name='lesson_edit'),
    path(C + 'lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),
    path(C + 'lessons/<int:lesson_id>/move/<str:direction>/', views.lesson_move, name='lesson_move'),
    path(C + 'lessons/<int:lesson_id>/resources/add/', views.resource_create, name='resource_create'),
    path(C + 'resources/<int:resource_id>/delete/', views.resource_delete, name='resource_delete'),

    path(C + 'quizzes/', views.quiz_list, name='quizzes'),
    path(C + 'quizzes/new/', views.quiz_form, name='quiz_create'),
    path(C + 'quizzes/<int:quiz_id>/edit/', views.quiz_form, name='quiz_edit'),
    path(C + 'quizzes/<int:quiz_id>/delete/', views.quiz_delete, name='quiz_delete'),
    path(C + 'quizzes/<int:quiz_id>/questions/', views.quiz_questions, name='quiz_questions'),
    path(C + 'quizzes/<int:quiz_id>/questions/new/', views.question_form, name='question_create'),
    path(C + 'quizzes/<int:quiz_id>/questions/<int:question_id>/', views.question_form, name='question_edit'),
    path(C + 'quizzes/<int:quiz_id>/questions/<int:question_id>/delete/', views.question_delete,
         name='question_delete'),

    path(C + 'students/', views.course_students, name='students'),
    path(C + 'analytics/', views.course_analytics, name='analytics'),
    path(C + 'reviews/', views.course_reviews, name='reviews'),
]
