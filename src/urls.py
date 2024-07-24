from django.conf.urls import url, include
from django.conf import settings

import proforma.views

urlpatterns = [
    # Index page
    #url(r'^$', RedirectView.as_view(pattern_name='task_list', permanent=True), name="index"),

# Proforma 2.0
    # official Proforma request
    url(r'^api/v2/submissions$', proforma.views.grade_api_v2, name="grade_api_v2"),
    # special solution for LON-CAPA (only task is ProFormA compatible)
    url(r'^api/v2/loncapasubmission$', proforma.views.grade_api_lon_capa, name="grade_api_lon_capa"),

    # external_grade common url: server / lms / function / domain / user / task

    url(r'^api/v2/upload$', proforma.views.upload_v2, name="upload_v2"),

    url(r'^api/v2/runtest$', proforma.views.runtest, name="runtest"),

    url(r'^version$', proforma.views.show_version, name="show_version"),
    url(r'^praktomat-info$', proforma.views.show_info, name="show_info"),
    url(r'^favicon\.ico$', proforma.views.icon, name="icon"),

]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]


# handle invalid URI as 404
urlpatterns += [
    url(r'^.*/$', proforma.views.error_page, name='error_page')
]