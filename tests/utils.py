import itertools
import unittest


class DataTestCase(unittest.TestCase):
    def assertJson(self, actual, expected, pos='@'):
        if callable(expected):
            # The reason this function exists
            try:
                ret = expected(actual)
            except AssertionError as e:
                raise AssertionError(
                    "Validation failed for %r at %s" % (actual, pos)
                ) from e
            else:
                if not ret:
                    raise AssertionError(
                        "Validation failed for %r at %s" % (actual, pos)
                    )
                return

        if type(actual) != type(expected):
            raise AssertionError(
                "Type mismatch: expected %r, got %r at %s" % (
                    type(expected), type(actual), pos,
                )
            )
        elif isinstance(actual, list):
            if len(actual) != len(expected):
                raise AssertionError(
                    "List lengths don't match: expected %d, got %d at %s" % (
                        len(expected), len(actual), pos,
                    )
                )
            for i, (a, e) in enumerate(zip(actual, expected)):
                self.assertJson(a, e, '%s[%d]' % (pos, i))
        elif isinstance(actual, dict):
            if actual.keys() != expected.keys():
                msg = "Dict keys don't match"
                if len(actual) != len(expected):
                    msg += "; expected %d, got %d at %s" % (
                        len(expected), len(actual), pos,
                    )
                if len(actual) > len(expected):
                    unexpected = set(actual) - set(expected)
                    msg += "\nUnexpected keys: "
                else:
                    unexpected = set(expected) - set(actual)
                    msg += "\nMissing keys: "
                if len(unexpected) > 3:
                    msg += ', '.join(
                        repr(key)
                        for key in itertools.islice(unexpected, 3)
                    )
                    msg += ', ...'
                else:
                    msg += ', '.join(repr(key)
                                     for key in unexpected)
                raise AssertionError(msg)
            for k, a in actual.items():
                e = expected[k]
                self.assertJson(a, e, '%s.%r' % (pos, k))
        else:
            self.assertEqual(actual, expected, msg="at %s" % pos)

    def assertCsvEqualNoOrder(self, actual, expected_header, expected_data):
        lines = actual.splitlines(False)
        self.assertEqual(lines[0], expected_header)
        self.maxDiff = None
        self.assertEqual(sorted(lines[1:]), sorted(expected_data))
