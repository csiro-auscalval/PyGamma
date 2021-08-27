from pathlib import Path

def append_suffix(path: Path, suffix: str) -> Path:
    """
    Append a suffix onto the end of a path, without removing existing suffixes.

    Note: This explicitly does NOT enforce any defactor suffix standards, such
    as the concept of a suffix needing to begin with a '.', as such this also
    supports our use-case of having '_' based suffixes for many files.

    >>> append_suffix(Path('/tmp/test_geo'), '_int').as_posix()
    '/tmp/test_geo_int'

    >>> append_suffix(Path('/tmp/test_geo.slc'), '.gz').as_posix()
    '/tmp/test_geo.slc.gz'
    """
    return path.parent / (path.name + suffix)

def par_file(slc_path: Path) -> Path:
    """
    Returns the .par file of an .slc/.mli file.

    A very common operation in gamma_insar is to get the .par file of an
    .slc or .mli file, this is a helper function to do that a little cleaner.

    >>> par_file(Path('test_geo.slc')).as_posix()
    'test_geo.slc.par'
    """
    assert(slc_path.suffix in [".slc", ".mli"])

    return append_suffix(slc_path, ".par")
