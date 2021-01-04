from unittest import mock
from datetime import datetime, timedelta
import pytest

import numpy as np

from insar.scripts.process_gamma import find_scenes_in_range, create_slave_coreg_tree

def _generate_dates(first_date, last_date, N=100):
    dt_diff = last_date - first_date
    coefs = np.linspace(0, 1, N).tolist()
    return [first_date + dt_diff*c for c in coefs]

today = datetime.now().date()
date_a = today - timedelta(days=200)
date_b = today + timedelta(days=200)

def test_scene_search_threshold():
    test_dates = _generate_dates(date_a, date_b)
    thres_days = 50

    lhs, rhs = find_scenes_in_range(today, test_dates, thres_days)
    found_dates = lhs + rhs

    # Make sure all found dates are within threshold
    for date in found_dates:
        assert(abs(date - today).days <= thres_days)

    # Make sure all test dates in threshold were found
    # and that those outside threshold were not
    for date in test_dates:
        if abs(date - today).days <= thres_days:
            assert(date in found_dates)
        else:
            assert(date not in found_dates)

    # Make sure LHS are left of reference date, and RHS are right
    for date in lhs:
        assert(date < today)

    for date in rhs:
        assert(date > today)


def test_tree_structure():
    test_dates = _generate_dates(date_a, date_b)
    thres_days = 50

    tree = create_slave_coreg_tree(today, test_dates, thres_days)

    master_dates = [today, today]
    last_level = test_dates

    # We should have a non-empty tree w/ non-empty data!
    assert(len(tree) > 0)

    for level in tree:
        # Shouldn't have any empty levels
        assert(len(level) > 0)

        # Should be within thres_days of our master dates
        for dt in level:
            lhs_dist = abs(dt - master_dates[0])
            rhs_dist = abs(dt - master_dates[1])

            assert(lhs_dist.days <= thres_days or rhs_dist.days <= thres_days)

        master_dates = [level[0], level[-1]]
        last_level = level
