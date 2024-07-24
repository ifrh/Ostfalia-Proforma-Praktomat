# coding=utf-8

import unittest
from palindrome import is_palindrome

# simple python test
class PalindromeNegativeTest(unittest.TestCase):

    _result = False

#    def setUp(self):
#        print('start unittest')
        

    def test_long(self):            
        self.assertEqual(False, is_palindrome('this is a long sentance'), 'this is a long sentance')    


    def test_short(self):            
        self.assertEqual(False, is_palindrome('hans'), 'hans')    
        self.assertEqual(False, is_palindrome('a b'), 'a b')    
