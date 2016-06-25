import sys
from pathlib import Path

path = Path(__file__)

# when moving virual environment, update following line
venv_location = str(path.parents[2])

# in Python3 there is no builtin execfile shortcut - let's define one
def execfile(filename):
    globals = dict( __file__ = filename)
    exec(open(filename).read(), globals)

# add application directory to execution path
sys.path.insert(0, str(path.parent))
sys.path.insert(0, str(path.parents[1]))

# activate virual environment
activate_this = venv_location + '/virtual_environment/bin/activate_this.py'
execfile(activate_this)

# import application to serve
from app import app as application
