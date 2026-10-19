from django.urls import path

from . import views

app_name = 'commerce'

urlpatterns = [
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:course_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:course_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('buy/<int:course_id>/', views.buy_now, name='buy_now'),
    path('enroll/<int:course_id>/', views.enroll_free, name='enroll_free'),
    path('orders/', views.order_history, name='orders'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/pay/', views.sandbox, name='sandbox'),
    path('orders/<str:order_number>/cancel/', views.cancel_order, name='cancel_order'),
]
