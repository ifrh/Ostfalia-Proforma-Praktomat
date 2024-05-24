package de.ostfalia.zell.isPalindromTask;

import static org.junit.Assert.*;

import java.util.concurrent.TimeUnit;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ErrorCollector;
//import static org.hamcrest.Matchers.equalTo;


import org.junit.FixMethodOrder;
import org.junit.runners.MethodSorters;

@FixMethodOrder(MethodSorters.NAME_ASCENDING)
public class PalindromTest {

    @Rule
    public ErrorCollector collector = new ErrorCollector(); 
    
    @Test
    public void testMultipleInput() {
        Object[][] mylist = {
                {"abc123321cbc", false}, 
                {"abc123321cba", true},
                {"121", true}, 
                {"123", false}
        };
                
        
        for (Object[] item : mylist) {          
            try
            {
                assertEquals("Test for " + item[0], item[1], MyString.isPalindrom(item[0].toString()));             
            }
            catch(Throwable e)
            {
                collector.addError(e);  
//              System.out.println("failed");
            }                       
          }         
    }
    
    
    @Test
    public void testLagertonnennotregal() {
        assertTrue("Lagertonnenregal mismatch", MyString.isPalindrom("Lagertonnennotregal"));
    }


    @Test
    public void testRentner() {
        // assertTrue( MyString.isPalindrom("Rentner"));
        assertEquals("Rentner", true, MyString.isPalindrom("Rentner"));
    }
        

    @Test
    public void testEmpty() {
    	String emptyString = "";
		assertEquals("tests StringHelper.isEmpty", true, StringHelper.isEmpty(emptyString));
    	
		try {
			TimeUnit.SECONDS.sleep(2);
		} catch (InterruptedException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		assertEquals("", true, MyString.isPalindrom(""));
        assertEquals(" ", true, MyString.isPalindrom(" "));
        assertEquals("  ", true, MyString.isPalindrom("  "));
        // assertTrue( MyString.isPalindrom(""));           
            
    }

    @Test
    public void testRandom() {
        assertEquals("abc123321cba", true, MyString.isPalindrom("abc123321cba"));
        //assertTrue( MyString.isPalindrom("abc123321cba"));            
            
    }

    @Test
    public void testFalse1() {
        assertEquals("abc123321cbc", false, MyString.isPalindrom("abc123321cbc"));
        //assertFalse( MyString.isPalindrom("abc123321cbc"));                       
    }

    @Test
    public void testFalse2() {
        assertEquals("abb", false, MyString.isPalindrom("abb"));        
        //assertFalse( MyString.isPalindrom("abb"));            
            
    }
    
}
