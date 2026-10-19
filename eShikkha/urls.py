from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('notifications/', include('notifications.urls')),
    path('courses/', include('courses.urls')),
    path('', include('learning.urls')),
    path('learn/', include('assessments.urls')),
    path('', include('commerce.urls')),
    path('teach/', include('studio.urls')),
    path('manage/', include('adminpanel.urls')),
    path('django-admin/', admin.site.urls),
]

if settings.DEBUG:
    # lesson videos and resources go through learning views (access checked)
    urlpatterns += [
        re_path(r'^media/(?P<path>(?:avatars|courses/thumbnails|courses/promo)/.+)$', serve,
                {'document_root': settings.MEDIA_ROOT}),
    ]

handler403 = 'core.views.permission_denied'
handler404 = 'core.views.page_not_found'
handler500 = 'core.views.server_error'
