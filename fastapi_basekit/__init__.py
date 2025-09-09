from importlib.metadata import version, PackageNotFoundError

__all__ = ["aio", "exceptions", "schema", "servicios"]

try:
    __version__ = version("fastapi-basekit")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"
