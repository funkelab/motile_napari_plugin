from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("motile-tracker")
except PackageNotFoundError:
    # package is not installed
    __version__ = "uninstalled"
