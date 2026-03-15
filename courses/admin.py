from django.contrib import admin
from .models import Course, Module

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0  # Number of empty module rows to show
    fields = ('title', 'content', 'video_label', 'quiz')
    readonly_fields = ()
    show_change_link = True

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_en')  # Show course ID and English title
    search_fields = ('title',)
    inlines = [ModuleInline]

    def title_en(self, obj):
        return obj.title.get('en', 'Untitled')
    title_en.short_description = "Title (EN)"

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'title_en')
    list_filter = ('course',)
    search_fields = ('title',)

    def title_en(self, obj):
        return obj.title.get('en', 'Untitled')
    title_en.short_description = "Title (EN)"