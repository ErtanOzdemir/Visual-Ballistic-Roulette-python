import unittest

from computations.utils.Helper import *


class TestHelper(unittest.TestCase):
    def test_convert_to_seconds(self):
        self.assertListEqual([1.0, 1.01, 1.02], Helper.convert_to_seconds([1000.0, 1010.0, 1020.0]))

    def test_print(self):
        self.assertEqual('+oo', Helper.print_val_or_infinity_symbol(30000000000))
        self.assertEqual('305', Helper.print_val_or_infinity_symbol(305))

    def test_last_value_in_front_ref(self):
        wheel_lap_times = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        ball_lap_time_in_front_of_ref = 12.5
        self.assertEqual(12.0,
                         Helper.get_last_time_wheel_is_in_front_of_ref(wheel_lap_times, ball_lap_time_in_front_of_ref))

    def test_compute_diff(self):
        #  In meter/second
        cumsum_times = [10.0, 11.0, 12.0, 13.0, 15.0]
        self.assertListEqual([1.0, 1.0, 1.0, 2.0], list(Helper.compute_diff(cumsum_times)))