import os, sys, tempfile
_tmp = tempfile.mkdtemp(prefix="ew-test-")
os.environ["EW_ARTIFACTS"] = _tmp
os.environ["EW_GRAPH"] = "ew_test"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
