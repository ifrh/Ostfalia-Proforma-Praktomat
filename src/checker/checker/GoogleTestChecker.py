# -*- coding: utf-8 -*-

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

    def run(self, env):
        # copy files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)

        # compile
        build_result = self.compile_make(env)
        if build_result != True:
            return build_result

        # remove source code files
        extensions = ('.c', '.C', '.hxx', '.hpp', '.h', '.cpp', '.cxx', '.o', '.a',
                      'CMakeCache.txt', 'Makefile', 'makefile', 'CMakeLists.txt', 'cmake_install.cmake')
        self.remove_source_files(env, extensions)

        # copy shared objects
        self.copy_shared_objects(env)

        # run test
        logger.debug('run ' + self.exec_command)
        cmd = [self.exec_command, '--gtest_output=xml']
        # get result
        (result, output) = self.run_command(cmd, env)
        if not result.passed:
            # error
            return result

        # XSLT
        xmloutput = self.convert_xml(env.tmpdir() + "/test_detail.xml")

        result.set_log(xmloutput, timed_out=False, truncated=False, oom_ed=False, log_format=CheckerResult.PROFORMA_SUBTESTS)
        return result
        
