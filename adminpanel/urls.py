from django.urls import path

from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('analytics/', views.analytics, name='analytics'),
    path('users/', views.users, name='users'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/suspend/', views.user_suspend, name='user_suspend'),
    path('users/<int:pk>/role/', views.user_role, name='user_role'),
    path('users/<int:pk>/grant/', views.user_grant, name='user_grant'),
    path('applications/', views.applications, name='applications'),
    path('applications/<int:pk>/decide/', views.application_decide, name='application_decide'),
    path('courses/', views.courses, name='courses'),
    path('courses/<int:pk>/', views.course_review, name='course_review'),
    path('courses/<int:pk>/moderate/', views.course_moderate, name='course_moderate'),
    path('courses/<int:pk>/feature/', views.course_feature, name='course_feature'),
    path('reviews/', views.reviews, name='reviews'),
    path('reviews/<int:pk>/toggle/', views.review_toggle, name='review_toggle'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:pk>/resolve/', views.report_resolve, name='report_resolve'),
    path('transactions/', views.transactions, name='transactions'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/refund/', views.order_refund, name='order_refund'),
    path('categories/', views.categories, name='categories'),
    path('categories/<int:pk>/', views.categories, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('tags/add/', views.tag_create, name='tag_create'),
    path('tags/<int:pk>/delete/', views.tag_delete, name='tag_delete'),
    path('announcements/', views.announcements, name='announcements'),
    path('announcements/<int:pk>/', views.announcements, name='announcement_edit'),
    path('announcements/<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
    path('settings/', views.platform_settings, name='settings'),
    path('audit/', views.audit_logs, name='audit'),
]
