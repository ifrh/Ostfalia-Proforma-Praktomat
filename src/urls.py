from django.urls import re_path, include
from django.conf import settings

import proforma.views

# Index page
# url(r'^$', RedirectView.as_view(pattern_name='task_list', permanent=True), name="index"),


urlpatterns = [

# Proforma 2.0
    # official Proforma request
    re_path(r'^api/v2/submissions$', proforma.views.grade_api_v2, name="grade_api_v2"),
    # special solution for LON-CAPA (only task is ProFormA compatible)
    re_path(r'^api/v2/loncapasubmission$', proforma.views.grade_api_lon_capa, name="grade_api_lon_capa"),

    # external_grade common url: server / lms / function / domain / user / task

    re_path(r'^api/v2/upload$', proforma.views.upload_v2, name="upload_v2"),

    re_path(r'^api/v2/runtest$', proforma.views.runtest, name="runtest"),

    re_path(r'^version$', proforma.views.show_version, name="show_version"),
    re_path(r'^praktomat-info$', proforma.views.show_info, name="show_info"),
    re_path(r'^tasks$', proforma.views.tasks, name="tasks"),
    re_path(r'^favicon\.ico$', proforma.views.icon, name="icon"),
    re_path(r'^error$', proforma.views.error_page, name="error"),

]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        re_path(r'^__debug__/', include(debug_toolbar.urls)),
    ]


# handle invalid URI as 404
handler404 = proforma.views.not_found_page
#urlpatterns += [
#    re_path(r'^.*/$', proforma.views.error_page, name='error_page')
#]