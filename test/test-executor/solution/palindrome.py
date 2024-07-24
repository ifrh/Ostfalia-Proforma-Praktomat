# coding=utf-8

import sys

def is_palindrome(text):
    print('is_palindrome ' + text)
    sys.stderr.write('to stderr')    
    text = text.lower()
    text = text.replace(' ', '')    
    reversestring = text[::-1]
    return reversestring == text