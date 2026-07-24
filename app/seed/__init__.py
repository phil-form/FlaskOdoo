import os
import glob
from pathlib import Path

from app.seed.user_seed import  UserSeed

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [UserSeed]

