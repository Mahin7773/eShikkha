from django.contrib import admin

from .models import Category, Course, Lesson, LessonResource, ModerationDecision, Review, Section, Tag


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'category', 'status', 'price', 'is_featured', 'updated_at')
    list_filter = ('status', 'category', 'level', 'is_featured')
    search_fields = ('title', 'instructor__username')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SectionInline]


admin.site.register([Category, Tag, Section, Lesson, LessonResource, ModerationDecision, Review])
