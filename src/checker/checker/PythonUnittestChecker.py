# -*- coding: utf-8 -*-
import os.path
import traceback

from lxml import etree

from checker.basemodels import CheckerResult, truncated_log
from utilities.file_operations import *
from checker.checker.ProFormAChecker import ProFormAChecker
from proforma import sandbox

import logging

logger = logging.getLogger(__name__)

class PythonUnittestChecker(ProFormAChecker):
    """ New Checker for Python Unittests. """
#    exec_command = models.CharField(max_length=200, help_text=_("executable name"))

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
						<xsl:when test="error">
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
								<xsl:when test="error">error</xsl:when>
								<xsl:when test="failure">error</xsl:when>
								<xsl:otherwise>info</xsl:otherwise>
							</xsl:choose>
						</xsl:attribute>
						<title><xsl:value-of select="../@name"/>.<xsl:value-of select="@name"/></title>
                        <xsl:choose>
                            <xsl:when test="failure">
                                <content format="plaintext">
                                    <xsl:value-of select="failure"/>
                                </content>
                            </xsl:when>
                            <xsl:when test="error">
                                <content format="plaintext">
                                    <xsl:value-of select="error"/>
                                </content>
                            </xsl:when>
                        </xsl:choose>													
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
        """ run testcase """
        # Precondition:
        # env already contains student's submission
        test_dir = env.tmpdir()
        logger.debug('main environment is in ' + test_dir)

        # copy task files and unzip zip file if submission consists of just a zip file.
        self.prepare_run(env)
        logger.debug('task code is in ' + test_dir)

        req_txt = sandbox.PythonImage.look_for_requirements_txt(test_dir)
        p_sandbox = sandbox.PythonImage(self, req_txt).get_container(test_dir)
        p_sandbox.upload_environmment()
        # precompile
        (passed, output) = p_sandbox.compile_tests()
        logger.debug("compilation passed is "+ str(passed))
        logger.debug(output)
        if not passed:
            return self.handle_compile_error(env, output, "", False, False)
        # run test
        result = self.create_result(env)
        (passed, output, timeout) = p_sandbox.runTests(image_suffix="pythonunit")
        if passed:
            p_sandbox.download_result_file()
        else:
            (output, truncated) = truncated_log(output)
            result.set_log(output, timed_out=timeout, truncated=truncated, oom_ed=False,
                           log_format=CheckerResult.TEXT_LOG)

        # XSLT
        if os.path.exists(test_dir + "/unittest_results.xml") and \
                os.path.isfile(test_dir + "/unittest_results.xml"):
            try:
                # f = open(test_dir + "/unittest_results.xml", "r")
                # logger.debug(f.read())

                xmloutput = self.convert_xml(test_dir + "/unittest_results.xml")
                result.set_log(xmloutput, timed_out=timeout, truncated=False, oom_ed=False,
                               log_format=CheckerResult.PROFORMA_SUBTESTS)
                result.set_extralog(output)
                return result
            except:
                logger.error('Error in XML transformation')
                traceback.print_exc()
                # logger.error(inst)
                # fallback: use default output
                return result
                # logger.error('could not convert to XML format')
                # raise Exception('Inconclusive test result (1)')
        else:
            if passed:
                # Test is passed but there is no XML file.
                # (exit in submission?)
                result.set_passed(False)
                result.set_log("Inconclusive test result", log_format=CheckerResult.TEXT_LOG)
                return result
                # raise Exception('Inconclusive test result (2)')
            return result
