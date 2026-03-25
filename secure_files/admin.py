from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from .services.firebase_storage import upload_file
from .models import SecureFile


@admin.register(SecureFile)
class SecureFileAdmin(admin.ModelAdmin):
    change_list_template = 'admin/secure_files/securefile/change_list.html'
    list_display = ('id', 'owner', 'original_name', 'size', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('owner__email', 'owner__username', 'original_name', 's3_key')
    autocomplete_fields = ('owner',)
    readonly_fields = ('uploaded_at',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'drag-upload/',
                self.admin_site.admin_view(self.drag_upload_view),
                name='secure_files_securefile_drag_upload',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['drag_upload_url'] = reverse('admin:secure_files_securefile_drag_upload')
        return super().changelist_view(request, extra_context=extra_context)

    def drag_upload_view(self, request):
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:secure_files_securefile_changelist'))

        file_list = request.FILES.getlist('files')
        if not file_list:
            single = request.FILES.get('file')
            if single:
                file_list = [single]

        if not file_list:
            self.message_user(request, 'No files selected.', level=messages.WARNING)
            return HttpResponseRedirect(reverse('admin:secure_files_securefile_changelist'))

        uploaded_count = 0
        for uploaded in file_list:
            try:
                upload_file(uploaded=uploaded, owner=request.user)
                uploaded_count += 1
            except ImproperlyConfigured as exc:
                self.message_user(request, f'Upload failed: {exc}', level=messages.ERROR)
                return HttpResponseRedirect(reverse('admin:secure_files_securefile_changelist'))
            except Exception as exc:
                self.message_user(request, f'Upload failed for {uploaded.name}: {exc}', level=messages.ERROR)
                return HttpResponseRedirect(reverse('admin:secure_files_securefile_changelist'))

        self.message_user(request, f'Successfully uploaded {uploaded_count} file(s).', level=messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:secure_files_securefile_changelist'))
