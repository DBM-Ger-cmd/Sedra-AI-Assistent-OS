import unittest
from app import greet

class GreetingTests(unittest.TestCase):
    def test_greeting(self):
        self.assertEqual(greet("David"), "Hello, David!")
