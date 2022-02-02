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

        build_result = self.compile_make(env)
        if build_result != True:
            return build_result

        extensions = ('.c', '.h', '.cpp', '.cxx')
        self.remove_source_files(env, extensions)
        logger.debug('exec_command ' + self.exec_command)

        # run test
        logger.debug('run ' + self.exec_command)
        cmd = [self.exec_command, '--gtest_output=xml']
        [output, error, exitcode, timed_out, oom_ed] = \
            execute_arglist(cmd, env.tmpdir(), timeout=settings.TEST_TIMEOUT, fileseeklimit=settings.TEST_MAXFILESIZE)
        # logger.debug(output)
        logger.debug("exitcode: " + str(exitcode))
        #if error != None:
        #    logger.debug("error: " + error)

        result = self.create_result(env)       
        if timed_out or oom_ed:
            # ERROR: Execution timed out
            logger.error('Execution timeout')
            # clear log for timeout
            # because truncating log will result in invalid XML.
            truncated = False
            output = '\Execution timed out... (Check for infinite loop in your code)\r\n' + output
            (output, truncated) = truncated_log(output)
            # Do not set timout flag in order to handle timeout only as failed testcase.
            # Student shall be motivated to look for error in his or her code and not in testcode.
            result.set_log(output, timed_out=False, truncated=truncated, oom_ed=oom_ed, log_format=CheckerResult.TEXT_LOG)
            result.set_passed(False)
            return result        
        
        # XSLT
        xmloutput = self.convert_xml(env.tmpdir() + "/test_detail.xml")
        
        result.set_log(xmloutput, timed_out=timed_out, truncated=False, oom_ed=oom_ed, log_format=CheckerResult.PROFORMA_SUBTESTS)
        result.set_passed(not exitcode)
        return result
        
