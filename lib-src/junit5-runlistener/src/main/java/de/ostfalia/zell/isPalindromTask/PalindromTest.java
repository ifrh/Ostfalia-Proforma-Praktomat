package de.ostfalia.zell.isPalindromTask;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@TestMethodOrder(MethodOrderer.Alphanumeric.class)
public class PalindromTest {


    @Test
    public void testLagertonnennotregal() {
        assertTrue( MyString.isPalindrom("Lagertonnennotregal"), "Lagertonnenregal mismatch");
    }


    @Test
    public void testRentner() {
        // assertTrue( MyString.isPalindrom("Rentner"));
        assertEquals(true, MyString.isPalindrom("Rentner"), "Rentner");
    }

}
