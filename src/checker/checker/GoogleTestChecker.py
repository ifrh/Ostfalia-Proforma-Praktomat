# -*- coding: utf-8 -*-
import os.path
import re
from lxml import etree

from django.db import models
from django.utils.translation import ugettext_lazy as _
from checker.basemodels import CheckerResult, truncated_log
# from utilities.safeexec import execute_arglist
from utilities.file_operations import *
from checker.checker.ProFormAChecker import ProFormAChecker
from proforma import sandbox

import logging
logger = logging.getLogger(__name__)

RXFAIL       = re.compile(r"^(.*)(FAILURES!!!|your program crashed|cpu time limit exceeded|ABBRUCH DURCH ZEITUEBERSCHREITUNG|Could not find class|Killed|failures)(.*)$",    re.MULTILINE)

class GoogleTestChecker(ProFormAChecker):
    """ New Checker for Google Test Unittests. """

    exec_command = models.CharField(max_length=200, help_text=_("executable name"))
    name = models.CharField(max_length=100, default='googletest', help_text=_("Name of the Testcase. To be displayed as title on Checker Results page"))

    def title(self):
        return "GoogleTest: " + self.name

    @staticmethod
    def description():
        return "This Checker runs a Testcases existing in the sandbox compiled with Googletest and Makefile."

    def output_ok(self, output):
        return (RXFAIL.search(output) == None)
        
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
						<xsl:when test="@status='run'">
							<score>1.0</score>
						</xsl:when>
						<xsl:otherwise/>
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

    # def submission_ok(self, env, RXSECURE):
    #     """ Check submission for invalid keywords """
    #     for (name, content) in env.sources():
    #         logger.debug('check ' + name)
    #         if RXSECURE.search(content):
    #             logger.error('invalid keyword found')
    #             return False
    #     return True

    def run(self, env):
        # copy files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)
        test_dir = env.tmpdir()

        # TODO
        # RXSECURE = re.compile(r"(exit|test_detail\.xml)", re.MULTILINE)
        # if not self.submission_ok(env, RXSECURE):
        #    result = self.create_result(env)
        #    result.set_passed(False)
        #    result.set_log("Invalid keyword found in submission (e.g. exit)", log_format=CheckerResult.TEXT_LOG)
        #    return result


        gt_sandbox = sandbox.CppImage(self).get_container(test_dir, self.exec_command)
        gt_sandbox.upload_environmment()
        # run test
        (passed, output) = gt_sandbox.compile_tests()
        logger.debug("compilation passed is "+ str(passed))
        logger.debug(output)
        if not passed:
            return self.handle_compile_error(env, output, "", False, False)
        (passed, output, timeout) = gt_sandbox.runTests(image_suffix="googletest")
        gt_sandbox.download_result_file()
        result = self.create_result(env)



        # compile
        # build_result = self.compile_make(env)
        # if build_result != True:
        #     return build_result

#         # remove source code files
#         extensions = ('.c', '.C', '.hxx', '.hpp', '.h', '.cpp', '.cxx', '.o', '.a',
#                       'CMakeCache.txt', 'Makefile', 'makefile', 'CMakeLists.txt', 'cmake_install.cmake')
#         self.remove_source_files(env, extensions)
#
#         # copy shared objects
#         self.copy_shared_objects(env)
#
#         # run test
#         logger.debug('run ' + self.exec_command)
#         cmd = [self.exec_command, '--gtest_output=xml']
#         # get result
#         (result, output) = self.run_command(cmd, env)
# #        if not result.passed:
#             # error
# #            return result

        (output, truncated) = truncated_log(output)

        logger.debug("passed is "+ str(passed))
        logger.debug(output)

        result.set_log(output, timed_out=timeout, truncated=truncated, oom_ed=False,
                       log_format=CheckerResult.TEXT_LOG)
        result.set_passed(passed and not truncated)
        # XSLT
        if os.path.exists(test_dir + "/test_detail.xml") and \
                os.path.isfile(test_dir + "/test_detail.xml"):
            try:
                xmloutput = self.convert_xml(test_dir + "/test_detail.xml")
                result.set_log(xmloutput, timed_out=timeout, truncated=False, oom_ed=False,
                               log_format=CheckerResult.PROFORMA_SUBTESTS)
                result.set_extralog(output)
                result.set_passed(passed)
            except:
                # fallback: use default output
                pass
                # return result
                # logger.error('could not convert to XML format')
                # raise Exception('Inconclusive test result (1)')
        else:
            if passed:
                # Test is passed but there is no XML file.
                # (exit in submission?)
                result.set_passed(False)
                result.set_log("Inconclusive test result", log_format=CheckerResult.TEXT_LOG)
                # return result
                # raise Exception('Inconclusive test result (2)')

        return result

