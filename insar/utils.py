import tempfile
import warnings
import weakref
import shutil
import types
import os


# Backport new TemporaryDirectory object

class TemporaryDirectory:
    """Create and return a temporary directory.  This has the same
    behavior as mkdtemp but can be used as a context manager.  For
    example:
        with TemporaryDirectory() as tmpdir:
            ...
    Upon exiting the context, the directory and everything contained
    in it are removed (unless delete=False is passed or an exception
    is raised during cleanup and ignore_cleanup_errors is not True).
    Optional Arguments:
        suffix - A str suffix for the directory name.  (see mkdtemp)
        prefix - A str prefix for the directory name.  (see mkdtemp)
        dir - A directory to create this temp dir in.  (see mkdtemp)
        ignore_cleanup_errors - False; ignore exceptions during cleanup?
        delete - True; whether the directory is automatically deleted.
    """

    def __init__(self, suffix=None, prefix=None, dir=None,
                 ignore_cleanup_errors=False, *, delete=True):
        self.name = tempfile.mkdtemp(suffix, prefix, dir)
        self._ignore_cleanup_errors = ignore_cleanup_errors
        self._delete = delete
        self._finalizer = weakref.finalize(
            self, self._cleanup, self.name,
            warn_message="Implicitly cleaning up {!r}".format(self),
            ignore_errors=self._ignore_cleanup_errors, delete=self._delete)

    @classmethod
    def _rmtree(cls, name, ignore_errors=False):
        def onexc(func, path, exc):
            if isinstance(exc, PermissionError):
                def resetperms(path):
                    try:
                        os.chflags(path, 0)
                    except AttributeError:
                        pass
                    os.chmod(path, 0o700)

                try:
                    if path != name:
                        resetperms(os.path.dirname(path))
                    resetperms(path)

                    try:
                        os.unlink(path)
                    # PermissionError is raised on FreeBSD for directories
                    except (IsADirectoryError, PermissionError):
                        cls._rmtree(path, ignore_errors=ignore_errors)
                except FileNotFoundError:
                    pass
            elif isinstance(exc, FileNotFoundError):
                pass
            else:
                if not ignore_errors:
                    raise

        shutil.rmtree(name, onexc=onexc)

    @classmethod
    def _cleanup(cls, name, warn_message, ignore_errors=False, delete=True):
        if delete:
            cls._rmtree(name, ignore_errors=ignore_errors)
            warnings.warn(warn_message, ResourceWarning)

    def __repr__(self):
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        if self._delete:
            self.cleanup()

    def cleanup(self):
        if self._finalizer.detach() or os.path.exists(self.name):
            self._rmtree(self.name, ignore_errors=self._ignore_cleanup_errors)

    #__class_getitem__ = classmethod(types.GenericAlias)
