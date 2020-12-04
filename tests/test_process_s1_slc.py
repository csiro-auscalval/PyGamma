from insar import process_s1_slc


# TODO: temporary until test harness is finalised
def test_create_slc_process():
    slc_proc = process_s1_slc.SlcProcess(
        "/tmp/dummy/raw_data_file",
        "/tmp/dummy/fake_output",
        "fake_polarisation",
        "20000301",
        "/tmp/fake/burst_data",
    )

    assert slc_proc
