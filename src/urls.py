from django.conf.urls import url, include
from django.views.generic.base import RedirectView
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
import sys
import os

import django.contrib.admindocs.urls
import tasks.views
import attestation.views
import solutions.views
import utilities.views
import accounts.urls
import tinymce.urls

from django.contrib import admin

urlpatterns = [
    # Index page
    url(r'^$', RedirectView.as_view(pattern_name='task_list', permanent=True), name="index"),

    # Admin
    url(r'^admin/tasks/task/(?P<task_id>\d+)/model_solution', tasks.views.model_solution, name="model_solution"),
    url(r'^admin/tasks/task/(?P<task_id>\d+)/final_solutions', tasks.views.download_final_solutions, name="download_final_solutions"),
    url(r'^admin/attestation/ratingscale/generate', attestation.views.generate_ratingscale, name="generate_ratingscale"),
    url(r'^admin/doc/', include(django.contrib.admindocs.urls)),
    url(r'^admin/', admin.site.urls),

    # Login and Registration
    url(r'^accounts/', include(accounts.urls)),

    # tinyMCE
    url(r'^tinymce/', include(tinymce.urls)),

    #Tasks
    url(r'^tasks/$', tasks.views.taskList, name = 'task_list'),
    url(r'^tasks/(?P<task_id>\d+)/$', tasks.views.taskDetail, name='task_detail'),

    # Solutions
    url(r'^solutions/(?P<solution_id>\d+)/$', solutions.views.solution_detail, name='solution_detail',kwargs={'full' : False}),
    url(r'^solutions/(?P<solution_id>\d+)/full/$', solutions.views.solution_detail, name='solution_detail_full', kwargs={'full': True}),
    url(r'^solutions/(?P<solution_id>\d+)/download$', solutions.views.solution_download, name='solution_download',kwargs={'full' : False}),
    url(r'^solutions/(?P<solution_id>\d+)/download/(?P<full>full)/$', solutions.views.solution_download, name='solution_download'),
    url(r'^solutions/(?P<solution_id>\d+)/run_checker$', solutions.views.solution_run_checker, name='solution_run_checker'),
    url(r'^tasks/(?P<task_id>\d+)/checkerresults/$', solutions.views.checker_result_list, name='checker_result_list'),
    url(r'^tasks/(?P<task_id>\d+)/solutiondownload$', solutions.views.solution_download_for_task, name='solution_download_for_task',kwargs={'full' : False}),
    url(r'^tasks/(?P<task_id>\d+)/solutiondownload/(?P<full>full)/$', solutions.views.solution_download_for_task, name='solution_download_for_task'),
    url(r'^tasks/(?P<task_id>\d+)/solutionupload/$', solutions.views.solution_list, name='solution_list'),
    url(r'^tasks/(?P<task_id>\d+)/solutionupload/user/(?P<user_id>\d+)$', solutions.views.solution_list, name='solution_list'),
    url(r'^tasks/(?P<task_id>\d+)/solutionupload/test/$', solutions.views.test_upload, name='upload_test_solution'),
    url(r'^tasks/(?P<task_id>\d+)/solutionupload/test/student/$', solutions.views.test_upload_student, name='upload_test_solution_student'),

    url(r'^tasks/(?P<task_id>\d+)/jplag$', solutions.views.jplag, name='solution_jplag'),

# Proforma add-on [start]
                       # Proforma 2.0
                       url(r'^api/v2/submissions$', 'proforma.views.grade_api_v2', name="grade_api_v2"),
                       # external_grade common url: server / lms / function / domain / user / task
                       # todo: username sollte @ enthalten
                       # file grader: function / user_name / task_id
                       #url(r'^external_grade/(?P<user_name>[\w\.@\-]{3,60})/(?P<task_id>\d{1,6})$',
                       #    'proforma.grade.file_grader', name='external_grade'),
                       # file grader: function / domain / user_name / task_id
                       #url(
                       #    r'^external_grade/(?P<domain>[a-zA-Z\_\.\d]{3,32})/\
                       #      (?P<user_name>[\w\.\@\-]{3,60})/(?P<task_id>\d{1,6})$',
                       #    'proforma.grade.file_grader', name='external_grade'),
                       # file grader: function / lms / domain / user_name / task_id
                       #url(
                       #    r'^external_grade/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<domain>[a-zA-Z\_\.\d]{3,32})/(?P<user_name>[\w\.\@\-]{3,60})/(?P<task_id>\d{1,6})$',
                       #    'proforma.grade.file_grader', name='external_grade'),
                       # file grader post
                       #url(
                       #    r'^external_grade/proforma/v1/task/(?P<task_id>\d{1,6})$', 'proforma.grade.file_grader_post'
                       #    , name='external_grade_files'),
                       # file grader post
                       # proforma internal
                       url(
                           r'^external_grade/(?P<response_format>[a-zA-Z\_\.\d]{3,32})/v1/task/(?P<task_id>\d{1,6})$', 'proforma.grade.file_grader_post'
                           , name='external_grade_files'),
                       # # text grader: function / lms / file_name / task_id
                       # url(
                       #     r'^external_grade_textfield/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<file_name>[a-zA-Z_\.\d]{3,250})/(?P<task_id>\d{1,6})$',
                       #     'proforma.grade.text_grader', name='external_grade_textfield'),
                       # # text grader: function / file_name / user_name / task_id
                       # url(
                       #     r'^external_grade_textfield/(?P<file_name>[a-zA-Z\_\.\d]{3,250})/(?P<user_name>[\w\.\@\-]{3,60})/(?P<task_id>\d{1,6})$',
                       #     'proforma.grade.text_grader', name='external_grade_textfield'),
                       # # text grader: function / lms / file_name / user_name / task_id
                       # url(
                       #     r'^external_grade_textfield/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<file_name>[a-zA-Z_\.\d]{3,250})/(?P<user_name>[\w\.\@\-]{3,60})/(?P<task_id>\d{1,6})$',
                       #     'proforma.grade.text_grader', name='external_grade_textfield'),
                       # # textfield grader
                       # url(
                       #     r'^textfield/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<file_name>[a-zA-Z_\.\d]{3,250})/(?P<task_id>\d{1,6})$',
                       #     'proforma.grade.text_grader', name='external_grade_textfield'),

                       # task

                       # # export as plain xml
                       # url(r'^export_task/(?P<task_id>\d{1,6})$', 'proforma.task.export',
                       #     name='export_task'),
                       # # export zip
                       # url(r'^export_task/(?P<task_id>\d{1,6})\.zip$', 'proforma.task.export', {'OutputZip':'TRUE'},
                       #     name='export_task'),
                       # # list all available tasks
                       # url(r'^export_task/list$', 'proforma.task.listTasks',
                       #     name='list_task'),
                       # list some details about specific task
                       # url(r'^export_task/detail/(?P<task_id>\d{1,6})$', 'proforma.task.detail',
                       #     name='export_task_detail'),
                       # # test_post
                       # url(r'^testPost$', 'proforma.task.test_post', name='testPost'),
                       # import task
                       # url(r'^activateTask/(?P<task_id>\d{1,6})$$', 'proforma.task.activateTasks',
                       #     name='activateTasks'),
                       # url(r'^importTaskObject$', 'proforma.task.importTaskObject',
                       #     name='importTaskObject'),
                       url(r'^importTask$', 'proforma.task.import_task',
                           name='importTask'),
                       # url(r'^importTaskObject/V2$', 'proforma.task.importTask_0_9_4',
                       #     name='importTask_0_9_4'),
                       # url(r'^importTaskObject/V1.01$', 'proforma.task.import_task',
                       #     name='importTaskObjectV1.01'),

# from old middleware
#                        url(
#                            r'^grade/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<lms_version>\d{1,6})/(?P<language>[a-zA-Z\_\.\d]{3,32})/'
#                            r'(?P<language_version>\d{1,6})/(?P<textfield_or_file>[a-zA-Z\_\.\d]{4,9})$'
#                            r'', proforma_views.grade_api_v1, name="grade"),
#                        url(
#                            r'^grade/(?P<lms>[a-zA-Z\_\.\d]{3,32})/(?P<lms_version>\d{1,6})/(?P<language>[a-zA-Z\_\.\d]{3,32})/'
#                            r'(?P<textfield_or_file>[a-zA-Z\_\.\d]{4,9})$'
#                            r'', proforma_views.grade_api_v1, name="grade"),
#                        url(
#                            r'^api/v1/grading/prog-languages/(?P<fw>[a-zA-Z\_\.\d]{3,32})/(?P<fw_version>\d{1,6})/submissions$'
#                            r'', proforma_views.grade_api_v1, name="grade_api_v1"),

                       url(r'^VERSION$', 'proforma.views.show_version', name="show_version"),

# Proforma add-on [end]	

    #Attestation
    url(r'^tasks/(?P<task_id>\d+)/attestation/statistics$', attestation.views.statistics, name='statistics'),
    url(r'^tasks/(?P<task_id>\d+)/attestation/$', attestation.views.attestation_list, name='attestation_list'),
    url(r'^tasks/(?P<task_id>\d+)/attestation/new$', attestation.views.new_attestation_for_task, name='new_attestation_for_task'),
    url(r'^solutions/(?P<solution_id>\d+)/attestation/new$', attestation.views.new_attestation_for_solution, name='new_attestation_for_solution', kwargs={'force_create' : False}),
    url(r'^solutions/(?P<solution_id>\d+)/attestation/new/(?P<force_create>force_create)$', attestation.views.new_attestation_for_solution, name='new_attestation_for_solution'),
    url(r'^attestation/(?P<attestation_id>\d+)/edit$', attestation.views.edit_attestation, name='edit_attestation'),
    url(r'^attestation/(?P<attestation_id>\d+)/withdraw$', attestation.views.withdraw_attestation, name='withdraw_attestation'),
    url(r'^attestation/(?P<attestation_id>\d+)/run_checker', attestation.views.attestation_run_checker, name='attestation_run_checker'),
    url(r'^attestation/(?P<attestation_id>\d+)$', attestation.views.view_attestation, name='view_attestation'),
    url(r'^attestation/rating_overview$', attestation.views.rating_overview, name='rating_overview'),
    url(r'^attestation/rating_export.csv$', attestation.views.rating_export, name='rating_export'),

    url(r'^tutorial/$', attestation.views.tutorial_overview, name='tutorial_overview'),
    url(r'^tutorial/(?P<tutorial_id>\d+)$', attestation.views.tutorial_overview, name='tutorial_overview'),

    # Uploaded media
    url(r'^upload/(?P<path>SolutionArchive/Task_\d+/User_.*/Solution_(?P<solution_id>\d+)/.*)$', utilities.views.serve_solution_file),
    url(r'^upload/(?P<path>TaskMediaFiles.*)$', utilities.views.serve_unrestricted),
    url(r'^upload/(?P<path>TaskHtmlInjectorFiles.*)$', utilities.views.serve_staff_only),
    url(r'^upload/(?P<path>jplag.*)$', utilities.views.serve_staff_only, name='jplag_download'),
    url(r'^upload/(?P<path>CheckerFiles.*)$', utilities.views.serve_staff_only),
    url(r'^upload/(?P<path>.*)$', utilities.views.serve_access_denied),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
