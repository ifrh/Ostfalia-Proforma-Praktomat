# -*- coding: utf-8 -*-
import os.path
import re
from lxml import etree

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import CheckerResult, truncated_log
from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from checker.checker.ProFormAChecker import ProFormAChecker

import logging

logger = logging.getLogger(__name__)

RXFAIL = re.compile(
    r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|failures)(.*)$",
    re.MULTILINE)


class PythonUnittestChecker(ProFormAChecker):
    """ New Checker for Python Unittests. """

    exec_command = models.CharField(max_length=200, help_text=_("executable name"))
#    name = models.CharField(max_length=100, default='googletest',
#                            help_text=_("Name of the Testcase. To be displayed as title on Checker Results page"))

#    def title(self):
#        return "GoogleTest: " + self.name

#    @staticmethod
#    def description():
#        return "This Checker runs a Testcases existing in the sandbox compiled with Googletest and Makefile."

#    def output_ok(self, output):
#        return (RXFAIL.search(output) == None)

    def convert_xml(self, filename):
        stylesheet = '''<?xml version="1.0"?>

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

        <xsl:output method="xml" version="1.0" indent="yes" omit-xml-declaration="yes" encoding="UTF-8"/>

	<xsl:template match="/testsuites">
		<subtests-response>
			<xsl:apply-templates select="testsuite/testcase"/>
		</subtests-response>
	</xsl:template>

	<xsl:template match="testcase">
		<subtest-response>
			<xsl:attribute name="id"><xsl:value-of select="../@name"/>.<xsl:value-of select="@name"/></xsl:attribute>

			<test-result>
				<result>
					<xsl:choose>
						<xsl:when test="failure">
							<score>0.0</score>
						</xsl:when>
						<xsl:otherwise>
							<score>1.0</score>
						</xsl:otherwise>						
					</xsl:choose>
				</result>
				<feedback-list>
					<student-feedback level="info">
						<xsl:attribute name="level">
							<xsl:choose>
								<xsl:when test="failure">error</xsl:when>
								<xsl:otherwise>info</xsl:otherwise>
							</xsl:choose>
						</xsl:attribute>
						<title><xsl:value-of select="../@name"/>.<xsl:value-of select="@name"/></title>
						<xsl:if test="failure">
							<content format="plaintext">
								<xsl:value-of select="failure"/>
							</content>
						</xsl:if>
					</student-feedback>
				</feedback-list>
			</test-result>
		</subtest-response>
	</xsl:template>

</xsl:stylesheet>
        '''
        xslt_root = etree.XML(stylesheet)
        transform = etree.XSLT(xslt_root)
        doc = etree.parse(filename)
        result_tree = transform(doc)
        return str(result_tree)

    def submission_ok(self, env, RXSECURE):
        """ Check submission for invalid keywords """
        for (name, content) in env.sources():
            logger.debug('check ' + name)
            if RXSECURE.search(content):
                logger.error('invalid keyword found')
                return False
        return True

    def run(self, env):
        # copy files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)
        test_dir = env.tmpdir()
        print(test_dir)

        # create run script:
        with open(test_dir + '/run_unit_test.py', 'w') as file:
            file.write("""# coding=utf-8
import unittest
import xmlrunner 
loader = unittest.TestLoader()
start_dir = '.'
suite = loader.discover(start_dir, "*test*.py") 
with open('unittest_results.xml', 'wb') as output:
    runner=xmlrunner.XMLTestRunner(output=output)
    runner.run(suite)          
""")
            os.chmod(test_dir + '/run_unit_test.py', 0o770)

        # TODO
        # RXSECURE = re.compile(r"(exit|test_detail\.xml)", re.MULTILINE)
        # if not self.submission_ok(env, RXSECURE):
        #    result = self.create_result(env)
        #    result.set_passed(False)
        #    result.set_log("Invalid keyword found in submission (e.g. exit)", log_format=CheckerResult.TEXT_LOG)
        #    return result

        # compile
        # build_result = self.compile_make(env)
        # if build_result != True:
        #    return build_result

        # remove source code files
        #extensions = ('.py')
        #self.remove_source_files(env, extensions)

        # copy python interpreter into sandbox
        copy_file('/usr/bin/python3', test_dir + '/python3')
        # copy_file('/usr/local/bin/pip', test_dir + '/pip3')
        self.copy_shared_objects(env)
        # python3 instead of 3.8 and prepare outside checker
        createpathonlib = "(cd / && tar -cf - usr/lib/python3.8) | (cd " + test_dir + " && tar -xf -)"
        os.system(createpathonlib)
        createpathonlib = "(mkdir " + test_dir + "/xmlrunner && cd / " + \
            "&& tar -cf - usr/local/lib/python3.8/dist-packages/xmlrunner) | " + \
            "(cd " + test_dir + " && tar -xf -)"
        print(createpathonlib)
        os.system(createpathonlib)

        cmd = ['./python3', 'run_unit_test.py']
        logger.debug('run ' + str(cmd))
        # get result
        (result, output) = self.run_command(cmd, env)

        # XSLT
        if os.path.exists(test_dir + "/unittest_results.xml") and \
                os.path.isfile(test_dir + "/unittest_results.xml"):
            try:
                xmloutput = self.convert_xml(test_dir + "/unittest_results.xml")
                result.set_log(xmloutput, timed_out=False, truncated=False, oom_ed=False,
                               log_format=CheckerResult.PROFORMA_SUBTESTS)
                result.set_extralog(output)
                return result
            except:
                # fallback: use default output
                return result
                # logger.error('could not convert to XML format')
                # raise Exception('Inconclusive test result (1)')
        else:
            if result.passed:
                # Test is passed but there is no XML file.
                # (exit in submission?)
                result.set_passed(False)
                result.set_log("Inconclusive test result", log_format=CheckerResult.TEXT_LOG)
                return result
                # raise Exception('Inconclusive test result (2)')
            return result

