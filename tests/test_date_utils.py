import pytest
import random
from datetime import date, timedelta

from insar.workflow.luigi.utils import merge_overlapping_date_ranges, simplify_dates

def rand_delta_days(stop = 300, start = 3):
    return timedelta(days=random.randrange(start, stop))


def rand_month(from_year = 2000, to_year = 2010):
    year = random.randint(from_year, to_year)
    month = random.randint(1, 12)

    if month == 12:
        result = (date(year, month, 1), date(year+1, 1, 1) - timedelta(days=1))
    else:
        result = (date(year, month, 1), date(year, month+1, 1) - timedelta(days=1))

    assert(result[1] >= result[0])
    return result


def iter_date_range(from_date, to_date):
    for i in range(int((to_date - from_date).days)):
        yield from_date + timedelta(days=i)


def rand_week(from_year = 2000, to_year = 2010):
    year = random.randint(from_year, to_year)
    week = random.randrange(0, 52)

    start = date(year, 1, 1) + timedelta(weeks=week)

    return (start, start + timedelta(days=6))


def test_overlapping_dates_get_merged():
    lhs = [date(2016, 1, 1), date(2016, 8, 1)]
    rhs = [date(2016, 6, 1), date(2017, 6, 1)]

    # Ensure two overlapping ranges result in a single merged range
    dates = [lhs, rhs]
    merged = merge_overlapping_date_ranges(dates)
    assert(len(merged) == 1)
    assert(merged[0][0] == lhs[0])
    assert(merged[0][1] == rhs[1])

    # Ensure no matter how many extra dates we add inbetween, that nothing changes
    for attempt in range(100):
        dates.append((lhs[0] + rand_delta_days(90), rhs[0] + rand_delta_days()))

        merged = merge_overlapping_date_ranges(dates)
        assert(len(merged) == 1)
        assert(merged[0][0] == lhs[0])
        assert(merged[0][1] == rhs[1])

    # Ensure range grows if we keep adding more
    dates = [lhs, rhs]
    for attempt in range(100):
        ext_left = (dates[-2][0] - rand_delta_days(20), dates[-2][0])
        ext_right = (dates[-1][1], dates[-1][1] + rand_delta_days(20))

        dates.append(ext_left)
        dates.append(ext_right)

        merged = merge_overlapping_date_ranges(dates)
        assert(len(merged) == 1)
        assert(merged[0][0] == ext_left[0])
        assert(merged[0][1] == ext_right[1])


def test_separate_dates_dont_get_merged():
    lhs = [date(2016, 1, 1), date(2016, 1, 15)]
    rhs = [date(2016, 2, 1), date(2016, 2, 15)]

    # Ensure two separate ranges don't get merged
    dates = [lhs, rhs]
    merged = merge_overlapping_date_ranges(dates)
    assert(len(merged) == 2)
    assert(merged[0] == lhs)
    assert(merged[1] == rhs)

    # Ensure no matter how many extra separate dates we add, that nothing changes
    three_weeks = timedelta(weeks=3)
    for attempt in range(1, 100):
        new_range = [rhs[0] + three_weeks * attempt, rhs[1] + three_weeks * attempt]
        dates.append(new_range)

        merged = merge_overlapping_date_ranges(dates)
        assert(len(merged) == attempt + 2)
        assert(merged[0] == lhs)
        assert(merged[1] == rhs)
        assert(merged[-1] == new_range)


def test_simplify_exclude_chops_off_lhs():
    date_range = (date(2016, 1, 1), date(2016, 6, 1))
    exclude = (date_range[0], date_range[0] + timedelta(weeks=4))

    simplified = simplify_dates([date_range], [exclude])
    assert(len(simplified) == 1)
    assert(simplified[0][0] == exclude[1] + timedelta(days=1))
    assert(simplified[0][1] == date_range[1])


def test_simplify_exclude_chops_off_rhs():
    date_range = (date(2016, 1, 1), date(2016, 6, 1))
    exclude = (date_range[1] - timedelta(weeks=4), date_range[1])

    simplified = simplify_dates([date_range], [exclude])
    assert(len(simplified) == 1)
    assert(simplified[0][0] == date_range[0])
    assert(simplified[0][1] == exclude[0] - timedelta(days=1))


def test_simplify_exclude_splits_date():
    date_range = (date(2016, 1, 1), date(2016, 6, 1))
    exclude = (date_range[0] + timedelta(weeks=4), date_range[1] - timedelta(weeks=4))

    simplified = simplify_dates([date_range], [exclude])
    assert(len(simplified) == 2)

    assert(simplified[0][0] == date_range[0])
    assert(simplified[0][1] == exclude[0] - timedelta(days=1))

    assert(simplified[1][0] == exclude[1] + timedelta(days=1))
    assert(simplified[1][1] == date_range[1])


def test_simplify_exclude_removes_all_dates():
    date_range = (date(2016, 1, 1), date(2016, 6, 1))

    simplified = simplify_dates([date_range], [date_range])
    assert(len(simplified) == 0)


def test_simplify_dates_fuzz():
    includes = [rand_month(2000, 2100) for _ in range(1000)]
    excludes = [rand_week(2000, 2100) for _ in range(1000)]

    simplified = simplify_dates(includes, excludes)

    # Assert all simplified dates are included, and not excluded
    for date_range in simplified:
        for date in iter_date_range(*date_range):
            num_includes = sum(date>=d1 and date<=d2 for d1,d2 in includes)
            num_excludes = sum(date>=d1 and date<=d2 for d1,d2 in excludes)

            assert(num_includes >= 1)
            assert(num_excludes == 0)
