# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2012-2019 Ostfalia University (eCULT-Team)
# http://ostfalia.de/cms/de/ecult/
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# SVN related code for 'old' interface

from django.conf import settings

import subprocess
import shutil
#import svn
#import svn.remote
import json
import os
import re
import requests
import logging
import tempfile
import urllib
import views

logger = logging.getLogger(__name__)

def check_system_svn():
    try:
        subprocess.check_output('svn')
    except subprocess.CalledProcessError:
        return False
    return True


def check_configured_svn(svn_server, svn_repository):
    # SVNURIACCESS Struct
    #    SVN-Server
    #       SVN-REPOSITORY
    #            SVNUSER
    #            SVNPASS
    try:
        if settings.SVNURIACCESS[svn_server][svn_repository] is not None:
            return True
    except KeyError:
            return False


def get_svn_credetials(svn_server, svn_repository):
    """
    get_svn_credetials checks the settings and returns the user and the pass
    :param svn_server: the svn-server
    :param svn_repository: the svn-repository
    :return: svn_user and svn_pass or it raises an exception
    """
    try:
        if 'SVNUSER' in settings.SVNURIACCESS[svn_server][svn_repository] and \
           'SVNPASS' in settings.SVNURIACCESS[svn_server][svn_repository]:
            svn_user = settings.SVNURIACCESS[svn_server][svn_repository].get('SVNUSER')
            svn_pass = settings.SVNURIACCESS[svn_server][svn_repository].get('SVNPASS')
            return svn_user, svn_pass
    except KeyError as err:
        raise err


def svn_to_zip(svn_uri, svn_user, svn_pass, submission_svn_rev=None):
    """
    svn_to_zip
    :param svn_uri: uri of the svn server
    :param svn_user: user
    :param svn_pass: pass
    :param submission_svn_rev:
    :return: fileobj -> zip of submission directory or exception
    """
    submission_directory = "submission-zip"
    remote = svn.remote.RemoteClient(svn_uri, username=svn_user, password=svn_pass)

    tmp_dir = tempfile.mkdtemp()
    remote.export(to_path=os.path.join(tmp_dir, submission_directory), revision=submission_svn_rev)
    to_zip = os.path.join(tmp_dir, submission_directory)

    try:
        tmp_archive = os.path.join(tmp_dir, 'archive')
        root_dir = to_zip
        submission_zip = shutil.make_archive(tmp_archive, 'zip', root_dir)
        submission_zip_fileobj = open(submission_zip, 'rb')
        return submission_zip_fileobj
    except IOError as e:
        raise IOError("IOError:", "An error occured while open zip-file", e)
    except Exception as e:
        raise Exception("SVNException:", "An error occured while creating zip: E125001: Couldn't determine absolute path of '.'")
    finally:
        shutil.rmtree(tmp_dir)



def get_group_rev(submission):
    """
    get_group_rev return a dict of the submission string
    :param submission: string "Gruppe=Value1;Rev=Value2"
    :return: dict of the items before and after = divided by ; or exception
    """
    # remove last;
    submission = submission.rstrip(';')
    try:
        submission_dict = dict(item.split("=") for item in submission.split(";"))
    except KeyError:
        raise KeyError("The submission must be in the format: Gruppe=<integer>;Rev=<integer>")
    except ValueError:
        raise ValueError("The submission must be in the format: Gruppe=<integer>;Rev=<integer>")
    return submission_dict


def send_result_to_gradebook(grade_result, labor_id, aufgaben_id, group, external_course_book_uri):

    status = False
    comment = ""
    xapi_auth_token = settings.EXTCOURSEBOOK.get(external_course_book_uri)
    headers = {'Content-type': 'application/json', 'X-API-Auth-Token': xapi_auth_token}

    match = re.search('<awarddetail>(?P<award>.+?)?<\/awarddetail>', grade_result)
    if match.group('award') == "EXACT_ANS":
        status = True

    json_data = {
                "labor": labor_id,
                "aufgabe": aufgaben_id,
                "data": {
                    "gruppe-" + str(group): {
                        "status": status,
                        "kommentar": comment
                    }
                }
            }
    try:
        r = requests.put(url=external_course_book_uri, headers=headers, json=json_data, verify=False)
        logger.info("json_data:" + json.dumps(json_data))
        logger.info("status_code: " + str(r.status_code) + "content: " + str(r.content))
    except Exception as e:
        logger.error("Exception: send_result_to_gradebook: " + str(type(e)) + str(e.args))


def get_svn_group(request):
    if not check_system_svn():
        raise Exception("svn is not installed on the server")
    # LON_CAPA special
    lc_submission = request.POST.get("LONCAPA_student_response")
    submission_svn_repository = request.POST.get("svn-repository")
    submission_svn_path = request.POST.get("svn-path")
    if not submission_svn_path:
        raise Exception("Please add a svn-path if you use svn-ostfalia")
    if not submission_svn_repository:
        raise Exception("Please add a svn-repository if you use svn-ostfalia")
    if lc_submission:
        submission_dict = get_group_rev(lc_submission)
        # we expect: Gruppe=<int>;Rev=<int>;
        if 'Gruppe' not in submission_dict:
            raise Exception("There as a problem with your group-name.")
        # if 'Rev' not in submission_dict:
        #    return HttpResponse(answer_format_template(award="ERROR", message="There as a problem with your SVN-Revision.",
        #                                     format=answer_format_form))
        try:
            submission_svn_group = int(submission_dict.get('Gruppe'))
        #    submission_svn_rev = int(submission_dict.get('Rev'))
        except Exception:
            raise Exception(
                "There as a problem with your group-name, revision, please read the description - all must be int")
    else:
        # todo ostfalia svn without LON-CAPA
        raise Exception("The group is missing")
    return submission_svn_group, submission_svn_path, submission_svn_repository


def grade_svn_submission(aufgaben_id, external_course_book, labor_id, request, submission_svn_group,
                         submission_svn_path, submission_svn_repository, task_id):
    submission_svn_server = "https://code.ostfalia.de"
    if not check_configured_svn(svn_repository=submission_svn_repository,
                                               svn_server=submission_svn_server):
        logger.exception("check_configured_svn\r\n" + str(submission_svn_repository) + "  " +
                         str(submission_svn_server))
        raise Exception("the configured svn-server and repository is not known to the middleware")
    try:
        submission_svn_user, submission_svn_pass = get_svn_credetials(
            svn_repository=submission_svn_repository,
            svn_server=submission_svn_server)
    except KeyError as err:
        raise Exception("There was a problem getting the user and the pass for the svn")
    # get Task svn_to_zip(svn_uri=None, submission_svn_rev=None, svn_directory=None):
    # SVN-URI = SVN-Server + submission_svn_repository + submission_svn_group
    # start grading todo gruppe -> Gruppe
    path = "svn/" + str(submission_svn_repository) + "/" + "Gruppe" + str(submission_svn_group) + "/" + \
           str(submission_svn_path) + "/src"
    submission_svn_uri = urllib.parse.urljoin(submission_svn_server, path)
    try:
        student_submission_zip_obj = svn_to_zip(svn_uri=submission_svn_uri, svn_user=submission_svn_user,
                                                               svn_pass=submission_svn_pass)
    except ValueError as e:
        raise Exception("Could not connect to svn -> remote.info got exception" + str(e))
    # start grading todo gruppe -> Gruppe
    submission_zip = {"Gruppe" + str(submission_svn_group) + ".zip": student_submission_zip_obj}
    # submission_zip = {'submission.zip': student_submission_zip_obj}
    grade_result = views.send_submission2external_grader(request=request, server=settings.GRADERV, taskID=task_id,
                                                   files=submission_zip)
    # if everything works we should end here
    if external_course_book:
        # todo should be startet with another thread -> parallel
        send_result_to_gradebook(grade_result, labor_id=labor_id, aufgaben_id=aufgaben_id,
                                                group=submission_svn_group,
                                                external_course_book_uri=external_course_book)
    return grade_result
