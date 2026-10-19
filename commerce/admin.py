from django.contrib import admin

from .models import Cart, CartItem, InstructorEarning, Order, OrderItem, PaymentTransaction


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'student', 'status', 'total', 'created_at', 'paid_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]


admin.site.register([Cart, CartItem, PaymentTransaction, InstructorEarning])
