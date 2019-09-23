package de.ostfalia.zell.praktomat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.text.NumberFormat;
import java.util.List;

import java.io.StringWriter;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

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


public class JunitProFormAListener extends RunListener {

	
    private final PrintStream writer;
    private Document doc = null;
    private Element subtestsResponse;
    private int counterFailed = 0;
    private String testClassname = "";
    
    private ByteArrayOutputStream baos = null; 
    
    
    // parameters of current test
    private boolean passed = true;
    private int counter = 0;
    Element score;
    Element feedbackList;
    Element studentFeedback;    
    

    public JunitProFormAListener() {
    	writer = System.out;
        // redirect stdout and stderr
        baos = new ByteArrayOutputStream();        
        System.setOut(new PrintStream(baos));           
        System.setErr(new PrintStream(baos));         	

    }

    public JunitProFormAListener(PrintStream writer) {
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
        xmlTitle.appendChild(doc.createTextNode(title));        

    	TestDescription annotation = description.getAnnotation(TestDescription.class);
    	if (annotation != null) {
        	String annoDescription = annotation.value();    
            if (!annoDescription.isEmpty()) {
                Element xmlDesc = doc.createElement("content");
                studentFeedback.appendChild(xmlDesc);    
                xmlDesc.appendChild(doc.createTextNode(annoDescription));                	
            }        	
    	}
       
      
    }

    @Override
    public void testFinished(Description description) {
        // todo: bei failed noch den Fehlertext
    	
    	String consoleOutput = baos.toString();
    	consoleOutput = consoleOutput.trim();
    	if (consoleOutput.length() > 0) {
    		//consoleOutput = consoleOutput.replace("&#13;", "\n");
    		
            Element feedback = doc.createElement("student-feedback");        
            feedbackList.appendChild(feedback);
            Element content = doc.createElement("content");
            content.setAttribute("format", "plaintext");        
            feedback.appendChild(content);                		
            content.appendChild(doc.createTextNode(consoleOutput));  
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
		try {
			testclass = Class.forName(this.testClassname);
	    	int i = 0;
	        for (StackTraceElement element : elements) {
				Class<?> clazz;
				clazz = Class.forName(element.getClassName());
				i++;
				if (testclass == clazz) {
					// found => remove tail
			    	StackTraceElement[] newStacktrace = new StackTraceElement[i];
			    	System.arraycopy( elements, 0, newStacktrace, 0, i);
			    	return newStacktrace;
				}
	        }			
		} catch (Exception e) {
			// TODO Auto-generated catch block
			//e.printStackTrace();
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
    	xmlTitle.appendChild(doc.createTextNode(title));        

    	Element xmlContent = doc.createElement("content");
    	xmlContent.setAttribute("format", "plaintext");        
    	xmlFeedback.appendChild(xmlContent);           		
    	xmlContent.appendChild(doc.createTextNode(content));      	
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
            	xmlFailure.appendChild(doc.createTextNode(exceptionText));
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
		JunitProFormAListener listener = new JunitProFormAListener();
		core.addListener(listener);
		listener.setTestclassname(args[0]);
				
		try {
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
		
        System.exit(0);			
	}    
}
