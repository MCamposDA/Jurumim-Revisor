"""
Desktop interface for Jurumim Revisor (started by initialize.py).

It builds Jurumim_Revisor.py command lines and runs them in a subprocess; the
command shown at the bottom of the window is the one that runs.

  comandos.py   interface state -> command line (no Tkinter, so it can be tested alone)
  app.py        the Tkinter window
"""
import importlib.util as _util
import os as _os

# Some conda environments (the gcc activation script) set this variable to a
# _sysconfigdata module that is not installed; pandas then fails to import with
# "C extension: _sysconfigdata_... not built". A name that does not exist is
# dropped here, before anything imports pandas, and so also for the commands
# the window starts.
for _var in ('_CONDA_PYTHON_SYSCONFIGDATA_NAME', '_PYTHON_SYSCONFIGDATA_NAME'):
    _nome = _os.environ.get(_var)
    if _nome and _util.find_spec(_nome) is None:
        del _os.environ[_var]
