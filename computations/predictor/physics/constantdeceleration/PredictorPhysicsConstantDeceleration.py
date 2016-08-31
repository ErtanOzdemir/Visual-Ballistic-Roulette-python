from HelperConstantDeceleration import *
from TimeSeriesMerger import *
from computations.predictor.Phase import *
from utils.Logging import *


class PredictorPhysicsConstantDeceleration(object):
    MEAN_SPEED_PER_REVOLUTION = None
    BALL_SPEEDS_LIST = None
    TIME_LIST = None

    @staticmethod
    def load_cache(database):
        """
        New convention is that the last ball lap times measure is done when the ball enters the diamonds ring.
        """
        bs_list = list()
        ts_list = list()
        for session_id in database.get_session_ids():
            ball_cum_sum_times = database.select_ball_lap_times(session_id)
            if len(ball_cum_sum_times) >= Constants.MIN_NUMBER_OF_BALL_TIMES_BEFORE_PREDICTION:
                ball_cum_sum_times = Helper.convert_to_seconds(ball_cum_sum_times)
                ball_diff_times = Helper.compute_diff(ball_cum_sum_times)
                bs_list.append(np.apply_along_axis(func1d=Helper.get_ball_speed, axis=0, arr=ball_diff_times))
                ts_list.append(ball_diff_times)

        mean_speed_per_revolution = np.nanmean(TimeSeriesMerger.merge(bs_list), axis=0)
        PredictorPhysicsConstantDeceleration.MEAN_SPEED_PER_REVOLUTION = mean_speed_per_revolution
        PredictorPhysicsConstantDeceleration.BALL_SPEEDS_LIST = np.array(bs_list)
        PredictorPhysicsConstantDeceleration.TIME_LIST = np.array(ts_list)

    @staticmethod
    def predict_most_probable_number(ball_cum_sum_times, wheel_cum_sum_times, debug=False):

        if len(wheel_cum_sum_times) < Constants.MIN_NUMBER_OF_WHEEL_TIMES_BEFORE_PREDICTION:
            raise SessionNotReadyException()

        if len(ball_cum_sum_times) < Constants.MIN_NUMBER_OF_BALL_TIMES_BEFORE_PREDICTION:
            raise SessionNotReadyException()

        ball_cum_sum_times = Helper.convert_to_seconds(ball_cum_sum_times)
        wheel_cum_sum_times = Helper.convert_to_seconds(wheel_cum_sum_times)

        most_probable_number = PredictorPhysicsConstantDeceleration.predict(ball_cum_sum_times,
                                                                            wheel_cum_sum_times,
                                                                            debug)
        return most_probable_number

    @staticmethod
    def predict(ball_cum_sum_times, wheel_cum_sum_times, debug):
        speeds_mean = PredictorPhysicsConstantDeceleration.MEAN_SPEED_PER_REVOLUTION
        bs_list = PredictorPhysicsConstantDeceleration.BALL_SPEEDS_LIST
        ts_list = PredictorPhysicsConstantDeceleration.TIME_LIST

        last_time_ball_passes_in_front_of_ref = ball_cum_sum_times[-1]
        last_wheel_lap_time_in_front_of_ref = Helper.get_last_time_wheel_is_in_front_of_ref(wheel_cum_sum_times,
                                                                                            last_time_ball_passes_in_front_of_ref)
        log('reference time of prediction = {} s'.format(last_time_ball_passes_in_front_of_ref), debug)
        ball_diff_times = Helper.compute_diff(ball_cum_sum_times)
        wheel_diff_times = Helper.compute_diff(wheel_cum_sum_times)
        ball_loop_count = len(ball_diff_times)

        # can probably match with the lap times. We de-couple the hyper parameters.
        speeds = np.apply_along_axis(func1d=Helper.get_ball_speed, axis=0, arr=ball_diff_times)
        # check all indices
        index_of_rev_start = HelperConstantDeceleration.compute_model_2(speeds, speeds_mean)
        index_of_last_known_speed = ball_loop_count + index_of_rev_start - 1

        matched_game_indices = TimeSeriesMerger.find_nearest_neighbors(speeds,
                                                                       bs_list,
                                                                       index_of_last_known_speed,
                                                                       neighbors_count=3)

        estimated_time_left = np.mean(np.sum(ts_list[matched_game_indices, (index_of_last_known_speed + 1):], axis=1))

        # very simple way to calculate it. Might be more complex.
        decreasing_factor = np.mean(np.array((bs_list[matched_game_indices] / np.hstack(
            [bs_list[matched_game_indices, 1:2] * 0 + 1, bs_list[matched_game_indices, :-1]]))[:, 1:]))

        # if we have [0, 0, 1, 2, 3, 0, 0], index_of_rev_start = 2, index_current_abs = 2 + 3 - 1 = 4
        qty_1 = bs_list[matched_game_indices, (index_of_last_known_speed + 1):].shape[1] - 1
        qty_2 = (np.mean(bs_list[matched_game_indices, -1] / bs_list[matched_game_indices, -2])) / decreasing_factor
        number_of_revolutions_left_ball = qty_1 + qty_2
        log('number_of_revolutions_left_ball = {}'.format(number_of_revolutions_left_ball))
        log('estimated_time_left = {}'.format(estimated_time_left))
        log('________________________________')

        # the speed values are always taken at the same diamond.
        diamond = HelperConstantDeceleration.detect_diamonds(number_of_revolutions_left_ball)
        log('diamond to be hit = {}'.format(diamond))

        if diamond == Constants.DiamondType.BLOCKER:
            expected_bouncing_shift = Constants.EXPECTED_BOUNCING_SHIFT_BLOCKER_DIAMOND
        else:
            expected_bouncing_shift = Constants.EXPECTED_BOUNCING_SHIFT_FORWARD_DIAMOND

        shift_ball_cutoff = (number_of_revolutions_left_ball % 1) * len(Wheel.NUMBERS)
        time_at_cutoff_ball = last_time_ball_passes_in_front_of_ref + estimated_time_left

        if time_at_cutoff_ball < last_time_ball_passes_in_front_of_ref + Constants.SECONDS_NEEDED_TO_PLACE_BETS:
            raise PositiveValueExpectedException()

        wheel_last_revolution_time = wheel_diff_times[-1]
        initial_phase = Phase.find_phase_number_between_ball_and_wheel(last_time_ball_passes_in_front_of_ref,
                                                                       last_wheel_lap_time_in_front_of_ref,
                                                                       wheel_last_revolution_time,
                                                                       Constants.DEFAULT_WHEEL_WAY)

        shift_between_initial_time_and_cutoff = ((estimated_time_left / wheel_last_revolution_time) % 1) * len(
            Wheel.NUMBERS)

        shift_to_add = shift_ball_cutoff + shift_between_initial_time_and_cutoff
        predicted_number_cutoff = Wheel.get_number_with_phase(initial_phase, shift_to_add, Constants.DEFAULT_WHEEL_WAY)
        log("shift_between_initial_time_and_cutoff = {}".format(shift_between_initial_time_and_cutoff), debug)
        log("predicted_number_cutoff is = {}".format(predicted_number_cutoff), debug)

        log("expected_bouncing_shift = {}".format(expected_bouncing_shift), debug)
        shift_to_add += expected_bouncing_shift
        predicted_number = Wheel.get_number_with_phase(initial_phase, shift_to_add, Constants.DEFAULT_WHEEL_WAY)
        log("predicted_number is = {}".format(predicted_number), debug)

        # possibility to assess the error on:
        # - PHASE 1
        # - number_of_revolutions_left_ball
        # - estimated_time_left
        # - PHASE 2 - if both quantities are correct, we can estimate predicted_number_cutoff exactly (without any
        # errors on the measurements).
        # - predicted_number_cutoff
        # - predicted_number (less important)
        # - diamond: FORWARD, BLOCKER, NO_DIAMOND (position of the diamond)

        # HYPER PARAMETER RELATION WITH QUANTITIES
        # - estimated_time_left (NOTHING) BALL SPEED IS NOT NEEDED.
        # - number_of_revolutions_left_ball (NOTHING) BALL SPEED IS NOT NEEDED.
        # - PHASE 2 - if both quantities are correct, we can estimate predicted_number_cutoff exactly (without any
        # errors on the measurements).
        # - initial_phase (NOTHING) WHEEL SPEED IS NOT NEEDED.
        # - predicted_number_cutoff
        # - predicted_number (less important)
        # - diamond: FORWARD, BLOCKER, NO_DIAMOND (position of the diamond)

        #     # constants to optimise.
        #   EXPECTED_BOUNCING_SHIFT_FORWARD_DIAMOND = 16
        #   EXPECTED_BOUNCING_SHIFT_BLOCKER_DIAMOND = 6
        #   MOVE_TO_NEXT_DIAMOND = 0  # due to the intrinsic speed. might change something. to be removed maybe later.
        #
        # Important
        # Actually we don't need BALL_SPEED, WHEEL_SPEED, CUTOFF_SPEED !
        return predicted_number
