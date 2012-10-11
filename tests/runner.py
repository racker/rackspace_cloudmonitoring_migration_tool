import unittest


def run_tests(path):
    loader = unittest.TestLoader()
    tests = loader.discover('%s' % path)
    testRunner = unittest.runner.TextTestRunner()
    testRunner.run(tests)
