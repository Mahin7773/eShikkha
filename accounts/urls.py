from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('welcome/', views.post_login, name='post_login'),
    path('profile/', views.profile, name='profile'),
    path('password/', views.change_password, name='password_change'),
    path('teach/', views.apply_instructor, name='apply_instructor'),
]
