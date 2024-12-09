from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("motile-plugin")
except PackageNotFoundError:
    # package is not installed
    __version__ = "uninstalled"
