# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import Checker
from checker.checker.CreateFileChecker import CreateFileChecker

import logging
logger = logging.getLogger(__name__)

class ProFormAChecker(Checker):
    """ Checker referencing Files (abstract class) """

    # Add fields to configure checker instances. You can use any of the Django fields. (See online documentation)

    proforma_id = models.CharField(default="None", max_length=255, help_text = _('Is needed for ProFormA'))

    files = models.ManyToManyField(CreateFileChecker, help_text=_("Files needed to run the test"))

    # class variable indicating if the tests shall get as much information about
    # subtests as possible (e.g. use RunListener for JUnit)
    retrieve_subtest_results = True

    # class variable for storing the XML response namespace
    NAMESPACES_V2_0 = 'urn:proforma:v2.0'
    NAMESPACES_V2_1 = 'urn:proforma:v2.1'
    xml_namespace = NAMESPACES_V2_1

    def copy_files(self, env):
        logger.debug('copy test files')
        for file in self.files.all():
            logger.debug('file: ' + file.file.path)
            file.run(env)
