"""One regression command, including existing function-style redaction tests."""
import bootstrap
import json
from pathlib import Path
import runpy
import unittest

def main():
    suite=unittest.TestSuite()
    for area in ('extraction','detection','integration'):
        suite.addTests(unittest.defaultTestLoader.discover(str(bootstrap.ROOT/'tests'/area),pattern='test_*.py'))
    for path in ('tests/redaction/test_redactor.py','tests/redaction/test_gate.py'):
        for name,test in runpy.run_path(str(bootstrap.ROOT/path)).items():
            if name.startswith('test_') and callable(test):suite.addTest(unittest.FunctionTestCase(test))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped)}
    out=bootstrap.ROOT/'output/reports/final_tests.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
