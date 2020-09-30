package de.ostfalia.zell.praktomat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.text.NumberFormat;
import java.util.List;

import java.io.StringWriter;
import java.io.UnsupportedEncodingException;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CharsetEncoder;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerConfigurationException;
import javax.xml.transform.TransformerException;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import org.junit.internal.JUnitSystem;
import org.junit.runner.Description;
import org.junit.runner.JUnitCore;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;
import org.junit.runner.notification.RunListener;

// support for Ostfalia JunitAddOn without needing to import classes from there:
//declare a new annotation named TestDescription
@Retention(RetentionPolicy.RUNTIME)
@interface TestDescription {
	String value();
}


public class Junit4ProFormAListener extends RunListener {

	
    private final PrintStream writer;
    private Document doc = null;
    private Element subtestsResponse;
    private int counterFailed = 0;
    private String testClassname = "";
    
    private ByteArrayOutputStream baos = null; 
    
    // allow 30kB char of text from stdout/stderr redirection
	final int maxStdoutLen = 30720;  
	private int stdoutLeft = maxStdoutLen;
    
    // parameters of current test
    private boolean passed = true;
    private int counter = 0;
    Element score;
    Element feedbackList;
    Element studentFeedback;    
    
    private boolean failureOutsideTest = false;    
    

    public Junit4ProFormAListener() throws UnsupportedEncodingException {
    	writer = System.out;
        // redirect stdout and stderr and force UTF-8 output
        baos = new ByteArrayOutputStream();        
        System.setOut(new PrintStream(baos, true, "UTF-8"));           
        System.setErr(new PrintStream(baos, true, "UTF-8"));         	

    }

    public Junit4ProFormAListener(PrintStream writer) {
        this.writer = writer;
    }

    public void setTestclassname(String testclassname) {
    	this.testClassname = testclassname;
    }
    
    @Override    
    public void testRunStarted(Description description) throws ParserConfigurationException {
        DocumentBuilderFactory docFactory = DocumentBuilderFactory.newInstance();
        DocumentBuilder docBuilder = docFactory.newDocumentBuilder();
        doc = docBuilder.newDocument();  
        
        //Element testResponse = doc.createElement("test-response");
        //doc.appendChild(testResponse);      
        subtestsResponse = doc.createElement("subtests-response");
        doc.appendChild(subtestsResponse);          
        //testResponse.appendChild(subtestsResponse);    
    	this.stdoutLeft = maxStdoutLen;
    }
    
/*    
    public void testRunAbortedWithException(Exception e) {
    String xml = "        <test-result>" + 
    		"          <result is-internal-error=\"true\">" + 
    		"            <score>0.0</score>" + 
    		"          </result>" + 
    		"          <feedback-list>" + 
    		"            <student-feedback level=\"debug\">" + 
    		"              <title>JUnit</title>\r\n" + 
    		"              <content format=\"html\">Fake Message</content>" + 
    		"            </student-feedback>" + 
    		"            <teacher-feedback level=\"debug\">" + 
    		"              <title>JUnit</title>" + 
    		"              <content format=\"plaintext\">content18</content>" + 
    		"            </teacher-feedback>" + 
    		"          </feedback-list>" + 
    		"        </test-result>";	
    }
    */
    
    @Override
    public void testRunFinished(Result result) {
        try {
			baos.close();
		} catch (IOException e1) {
			// TODO Auto-generated catch block
			e1.printStackTrace();
		}

        
        if (this.failureOutsideTest) {
        	// no xml creation
        	return;
        }
        
    	
        // Transform Document to XML String
        TransformerFactory tf = TransformerFactory.newInstance();
        Transformer transformer;
		try {
			transformer = tf.newTransformer();
	        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
	        transformer.setOutputProperty(OutputKeys.INDENT, "yes");
	        transformer.setOutputProperty(OutputKeys.ENCODING, "utf-8");	        
	        StringWriter xmlWriter = new StringWriter();
	        DOMSource root = new DOMSource(doc);
	        transformer.transform(root, new StreamResult(writer));
	        
	        // print the String value of final xml document        
	        getWriter().println(xmlWriter.getBuffer().toString());    				
		} catch (TransformerException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
	        getWriter().print(e.getMessageAndLocation());    				
		}

        
//        printHeader(result.getRunTime());
    }

    // -------------------------------
    
    @Override
    public void testStarted(Description description) {
    	String title = "";
    	String descTitle = new String(description.toString());
    	
    	descTitle = descTitle.substring(0, descTitle.indexOf("("));
        for (String w : descTitle.split("(?<!(^|[A-Z]))(?=[A-Z])|(?<!^)(?=[A-Z][a-z])")) {
        	if (title.isEmpty() && w.equalsIgnoreCase("test"))
        		continue;
        	
        	title += w + ' ';
        }    

        title = title.trim();
        passed = true;   
        counter ++;
        
    	// create xml 
    	
    	
        /*<subtest-response id = 's1'>
          <test-result>        
        
            <result><score>1.0</score></result>
          
            <feedback-list>
              <student-feedback level="info">
                <title>Even Number Of Characters</title>
              </student-feedback>
            </feedback-list>

        </test-result>
        </subtest-response>*/
    
        Element subtestResponse = doc.createElement("subtest-response");
        subtestResponse.setAttribute("id", "junit" +  counter);
        subtestsResponse.appendChild(subtestResponse);
        
        // Create First Name Element
        Element testResult = doc.createElement("test-result");
        subtestResponse.appendChild(testResult);
        
        Element result = doc.createElement("result");
        testResult.appendChild(result);
        score = doc.createElement("score");
        result.appendChild(score);
    	
        feedbackList = doc.createElement("feedback-list");
        testResult.appendChild(feedbackList);
        
        
        studentFeedback = doc.createElement("student-feedback");        
        feedbackList.appendChild(studentFeedback);
        
        Element xmlTitle = doc.createElement("title");
        studentFeedback.appendChild(xmlTitle);    
        xmlTitle.appendChild(doc.createTextNode(cleanXmlUtf8Char(title)));        

    	TestDescription annotation = description.getAnnotation(TestDescription.class);
    	if (annotation != null) {
        	String annoDescription = annotation.value();    
            if (!annoDescription.isEmpty()) {
                Element xmlDesc = doc.createElement("content");
                studentFeedback.appendChild(xmlDesc);    
                xmlDesc.appendChild(doc.createTextNode(cleanXmlUtf8Char(annoDescription)));                	
            }        	
    	}
       
      
    }

    private String cleanXmlUtf8Char(String text) {
		// replace invalid UTF-16/XML char by '[?]' 
		// Note that Java uses UTF-16 as internal representation for Strings!
    	// https://docs.oracle.com/javase/8/docs/api/java/lang/Character.html
    	
    	// Problem: Some of the invalid characters are escaped. These
    	// escaped characters can result in problems in the receiver of the 'message'
    	// because they are still invalid.
    	
    	// UTF-8 (used for xml) Codepoint range is U+0000 to U+10FFFF.   	
   	
    	// https://stackoverflow.com/questions/4237625/removing-invalid-xml-characters-from-a-string-in-java
    	// So we must find invalid characters in UTF-16.
    	// We also replace invalid XML 1.0 char in order to avoid further problems.
    	// XML 1.0
    	// #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
	    final String xml10pattern = "[^"
	            + "\u0009\r\n"
	            + "\u0020-\uD7FF"
	            // U+D800 to U+DFFF is reserved in UTF-16 (Wikipedia): 
	            // The Unicode standard permanently reserves these code 
	            // point values for UTF-16 encoding of the high and low surrogates.
	            + "\uE000-\uFFFD"
	            + "\ud800\udc00-\udbff\udfff"
	            + "]";
	
    
    	return text.replaceAll(xml10pattern, "[?]");
    }
    
    
    private String multiByteSubstr(String original, int length)  {
    	// return original.substring(0, original.offsetByCodePoints(0, length));
    	return original.substring(0, length);
    }
    
    @Override
    public void testFinished(Description description) {
        // todo: bei failed noch den Fehlertext
    	// trim text that is written to stdout/err during test run.
    	
    	String consoleOutput = baos.toString();
    	consoleOutput = consoleOutput.trim();
    	if (consoleOutput.length() > 0) {
    		// avoid having a lot of extra text because of redirecting stdout/stderr
    		if (consoleOutput.length() > this.stdoutLeft) {
				consoleOutput = this.multiByteSubstr(consoleOutput, this.stdoutLeft) + "... [truncated]";
    		}
			this.stdoutLeft -=  consoleOutput.length();
			if (this.stdoutLeft < 0) {
				this.stdoutLeft = 0;				
			}
  		
            Element feedback = doc.createElement("student-feedback");        
            feedbackList.appendChild(feedback);
            Element content = doc.createElement("content");
            content.setAttribute("format", "plaintext");        
            feedback.appendChild(content);                		
            content.appendChild(doc.createTextNode(cleanXmlUtf8Char(consoleOutput)));  
    	}
        baos.reset();

    	if (passed) {
            score.appendChild(doc.createTextNode("1.0"));    		
            studentFeedback.setAttribute("level", "info");
        }
    	else {
            score.appendChild(doc.createTextNode("0.0"));            		
            studentFeedback.setAttribute("level", "error");
    	}
    }
    
    private StackTraceElement[]  stripStackTrace(StackTraceElement[] elements) { 
    	Class<?> testclass;
    	final int maxTraceElments = 10;
		try {
			testclass = Class.forName(this.testClassname);
	    	int i = 0;
	        for (StackTraceElement element : elements) {
				Class<?> clazz;
				clazz = Class.forName(element.getClassName());
				i++;
				if (testclass == clazz || i == maxTraceElments) {
					// found => remove tail
			    	StackTraceElement[] newStacktrace = new StackTraceElement[i];
			    	System.arraycopy( elements, 0, newStacktrace, 0, i);
			    	return newStacktrace;
				}
	        }			
		} catch (Exception e) {
			// TODO Auto-generated catch block
			//writer.append("***CANNOT STRIP STACK TRACE\n");
			//writer.append("Testclass: " + this.testClassname + "\n");
			//writer.append("Exception: " + e.getMessage() + "\n");				
			//writer.append("Exception: " + e.toString() + "\n");				
			//e.fillInStackTrace().printStackTrace(writer);				
			// e.printStackTrace();
			
			// this version needs accessClassInPackage.sun.nio.fs
		    // when using policy manager			
			try {
				// in case of an error simply deliver first 10 elements of stack trace				
				final int max = maxTraceElments;
		    	StackTraceElement[] newStacktrace = new StackTraceElement[max];
		    	System.arraycopy( elements, 0, newStacktrace, 0, max);
		    	return newStacktrace;	 										
			} catch (Exception f) {
				return elements;    	
			}
		}
    	
		return elements;    	
    }
    
    private void createFeedback(String title, String content, boolean teacher) {
    	Element xmlFeedback = null;
    	if (teacher)
    		xmlFeedback = doc.createElement("teacher-feedback");
    	else 
    		xmlFeedback = doc.createElement("student-feedback");
    		
        feedbackList.appendChild(xmlFeedback);
        
    	Element xmlTitle = doc.createElement("title");
    	xmlFeedback.appendChild(xmlTitle);    
    	xmlTitle.appendChild(doc.createTextNode(cleanXmlUtf8Char(title)));        

    	Element xmlContent = doc.createElement("content");
    	xmlContent.setAttribute("format", "plaintext");        
    	xmlFeedback.appendChild(xmlContent);           		
    	xmlContent.appendChild(doc.createTextNode(cleanXmlUtf8Char(content)));      	
    }
    
    @Override
    public void testFailure(Failure failure) {
    	Description d = failure.getDescription();
        //String failureText = failure.toString();
        String message = failure.getMessage();
        String testHeader = failure.getTestHeader();
        Throwable exception  = failure.getException();
        //Throwable cause1 = exception.getCause();
        
        String exceptionText = exception.toString(); // name of exception
           
        
        boolean showStackTraceToStudent = true;
        StackTraceElement[] strippedStacktrace = this.stripStackTrace(failure.getException().getStackTrace());
        String stackTraceString = "";
        for (StackTraceElement s : strippedStacktrace) {
        	stackTraceString = stackTraceString + s.toString() + "\n";
        }  
        stackTraceString = stackTraceString +  "[...]\n";
        
    	if (studentFeedback == null) {
    		this.failureOutsideTest = true;
    		writer.println(failure);
    		writer.println("");
    		writer.println(stackTraceString);        		
    		return;    		
    	}          
        
        if (strippedStacktrace.length > 0) {
        	if (strippedStacktrace[0].getClassName().startsWith("org.junit.")) {
        		// Function Error in Test Code
        		// => do not show stack trace to student
        		showStackTraceToStudent = false;
        		exceptionText = message; 
        	} else {
        		// assume coding error: 
        		// check if the exception occured inside student code
                // this.createFeedback("Stack Trace", stackTraceString, false);        		
        	}
        } 
        
           	
    	// create student feedback        
        if (exceptionText != null) {
        	if (studentFeedback.getElementsByTagName("content").getLength() == 0) {
        		// append content to existing student-feedback
                Element xmlFailure = doc.createElement("content");
                xmlFailure.setAttribute("format", "plaintext");        
                studentFeedback.appendChild(xmlFailure);
            	xmlFailure.appendChild(doc.createTextNode(cleanXmlUtf8Char(exceptionText)));
            	//xmlFailure.appendChild(doc.createTextNode("EXCEPTION TEXT: " + exceptionText));
        	} else {
                this.createFeedback("", exceptionText, false); // no title        		
        	}
        	
        	
        } else {
            // this.createFeedback("Exception text", "N/A", true);
        }

        
        // create teacher feedback with additional stack trace
        //this.createFeedback("Message", exceptionText, true);
        this.createFeedback("Stack Trace:", stackTraceString, !showStackTraceToStudent);
        
/*        
        Element teacherFeedback = doc.createElement("teacher-feedback");        
        feedbackList.appendChild(teacherFeedback);
        
        	Element xmlTitle = doc.createElement("title");
        	teacherFeedback.appendChild(xmlTitle);    
        	xmlTitle.appendChild(doc.createTextNode("Stack Trace"));        

        	Element xmlException = doc.createElement("content");
        	xmlException.setAttribute("format", "plaintext");        
        	teacherFeedback.appendChild(xmlException);    
        	String teacherText = "";
        	teacherText = exceptionText + "\n" + failure.getTrace();        
        		
        	xmlException.appendChild(doc.createTextNode(teacherText));  
*/        
        
        passed = false;  
        counterFailed++;      
    }

    // -------------------------------
    
    
    
    
    @Override
    public void testIgnored(Description description) {
        //writer.append('I');
    }

    /*
      * Internal methods
      */

    private PrintStream getWriter() {
        return writer;
    }


    protected void printFailures(Result result) {
        List<Failure> failures = result.getFailures();
        if (failures.isEmpty()) {
            return;
        }
               
        
        int i = 1;
        for (Failure each : failures) {
            printFailure(each, "" + i++);
        }
    }

    protected void printFailure(Failure each, String prefix) {
        getWriter().println(prefix + " " + each.getMessage());
        //getWriter().print(each.getTrimmedTrace());
    }

    protected void printFooter(Result result) {
        getWriter().println();
        
        float score = ((float)(counter - counterFailed))/counter;
        getWriter().print("Score: " + score);
    	
/*        
        if (result.wasSuccessful()) {
            getWriter().println();
            getWriter().print("OK");
            getWriter().println(" (" + result.getRunCount() + " test" + (result.getRunCount() == 1 ? "" : "s") + ")");

        } else {
            getWriter().println();
            getWriter().println("FAILURES!!!");
            getWriter().println("Tests run: " + result.getRunCount() + ",  Failures: " + result.getFailureCount());
        }
        getWriter().println();
*/        
    }
    
/*    protected testRunFinished(Result result) {
    	
    }
*/
    /**
     * Returns the formatted string of the elapsed time. Duplicated from
     * BaseTestRunner. Fix it.
     */
    protected String elapsedTimeAsString(long runTime) {
        return NumberFormat.getInstance().format((double) runTime / 1000);
    }
    
    public static void main(String[] args) {
        if (args.length == 0) {
        	System.err.println("Invalid argument number. Usage: program testclass (without extension)");
        	// sample:
        	// proforma.MyStringTest
        	// de.ostfalia.gdp.ss19.s1.KegelVolumenTest
        	// de.ostfalia.zell.isPalindromTask.PalindromTest
	        System.exit(1);			 			
        }
        PrintStream originalOut = System.out;
        PrintStream originalErr = System.err;
        
		JUnitCore core= new JUnitCore();
		Junit4ProFormAListener listener = null;
				
		try {
			listener = new Junit4ProFormAListener();
			core.addListener(listener);
			listener.setTestclassname(args[0]);
			
			core.run(Class.forName(args[0]));
		} catch (ClassNotFoundException e) {
			// reset redirection
	        System.setOut(originalOut);           
	        System.setErr(originalErr);    
	        
			System.err.println("JUnit entry point not found: " + e.getMessage());
	    	//System.out.println("Usage: program testclass (without extension)");
	        System.exit(1);			 			
		} catch (Exception e) {
			// reset redirection
	        System.setOut(originalOut);           
	        System.setErr(originalErr);    
	        
			System.err.println(e.getMessage());
	        System.exit(1);				
		}
		
		if (listener != null && listener.failureOutsideTest) 
	        System.exit(1);
		
        System.exit(0);			
	}    
}
