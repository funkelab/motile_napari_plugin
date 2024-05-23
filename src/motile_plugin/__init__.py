from importlib.metadata import PackageNotFoundError, version

from .widgets.motile_widget import MotileWidget

try:
    __version__ = version("motile-toolbox")
except PackageNotFoundError:
    # package is not installed
    __version__ = "uninstalled"

__all__ = ("MotileWidget",)
