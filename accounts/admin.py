from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import InstructorApplication, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Platform', {'fields': ('role', 'headline', 'bio', 'avatar', 'website', 'suspended_at', 'suspension_reason')}),
    )


@admin.register(InstructorApplication)
class InstructorApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'expertise', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status',)
