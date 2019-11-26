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

    files = models.ManyToManyField(CreateFileChecker, help_text=_("Files needed to run the test"))

    def copy_files(self, env):
        logger.debug('copy test files')
        for file in self.files.all():
            file.run(env)
