# We base the 20211208 proxy off of the 20210701 release
from insar.gamma.versions.v20210701 import PyGammaProxy as PyGammaProxy_v20210701


class PyGammaProxy(PyGammaProxy_v20210701):
    pass

    # There are no major changes that we care about in this release right now
    #
    # there have been "extra" features added to programs like gc_map2 and SLC_ovr we might care about,
    # but they're optional / opt-in, thus no changes needed unless we decide we need to use them (in that
    # case the work is actually in the older versions back-porting any of that if possible/required).
