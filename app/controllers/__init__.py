import os
import glob
from pathlib import Path

# print(os.path.dirname(__file__))
# print(os.path.dirname(__file__) + "/*.py")
# print(glob.glob(os.path.dirname(__file__) + "/*.py"))
# print([os.path.basename(f)[:-3] for f in glob.glob(os.path.dirname(__file__) + "/*.py")])
# __all__ = [os.path.basename(f)[:-3] for f in glob.glob(os.path.dirname(__file__) + "/*.py")]

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]