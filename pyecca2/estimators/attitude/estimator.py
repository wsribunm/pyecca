import time

import numpy as np

import pyecca2.msgs as msgs
import pyecca2.uros as uros


class AttitudeEstimator:
    """
    An attitude estimator node for uros
    """

    def __init__(self, core, name, eqs):
        self.core = core

        # subscriptions
        self.sub_imu = uros.Subscriber(core, 'imu', msgs.Imu, self.imu_callback)
        self.sub_mag = uros.Subscriber(core, 'mag', msgs.Mag, self.mag_callback)

        # publications
        self.pub_est = uros.Publisher(core, name + '_status', msgs.EstimatorStatus)
        self.pub_state = uros.Publisher(core, name + '_state', msgs.VehicleState)

        self.msg_est_status = msgs.EstimatorStatus()
        self.msg_state = msgs.VehicleState()

        self.sub_params = uros.Subscriber(core, 'params', msgs.Params, self.params_callback)
        self.param_list = []
        self.x = eqs['constants']()['x0']
        self.W = eqs['constants']()['W0']
        self.n_x = self.x.shape[0]
        self.n_e = self.W.shape[0]
        self.t_last_imu = 0
        self.eqs = eqs

    def params_callback(self, msg):
        for p in self.param_list:
            p.update()

    def mag_callback(self, msg):
        y = np.array([1, 2, 3])
        self.x, self.W = self.eqs['correct_mag'](self.x, self.W, y)

    def imu_callback(self, msg):

        # compute dt
        t = msg.data['time']
        dt = t - self.t_last_imu
        self.t_last_imu = t

        # estimate state
        omega = msg.data['gyro']

        start = time.thread_time()
        std_gyro = 1e-2
        sn_gyro_rw = 1e-2

        if dt > 0:
            self.x, self.W = self.eqs['predict'](t, self.x, self.W, omega, std_gyro, sn_gyro_rw, dt)
        q, b_g = self.eqs['get_state'](self.x)
        end = time.thread_time()
        elapsed = end - start

        # correct

        # publish vehicle state
        self.msg_state.data['time'] = t
        self.msg_state.data['q'] = q.T
        self.msg_state.data['b'] = b_g.T
        self.msg_state.data['omega'] = omega.T
        self.pub_state.publish(self.msg_state)

        # publish estimator status
        self.msg_est_status.data['time'] = t
        self.msg_est_status.data['n_x'] = self.n_x
        self.msg_est_status.data['x'][:self.n_x] = self.x.T
        W_vect = np.reshape(np.array(self.W)[np.diag_indices(self.n_e)], -1)
        self.msg_est_status.data['W'][:len(W_vect)] = W_vect
        self.msg_est_status.data['elapsed'] = elapsed
        self.pub_est.publish(self.msg_est_status)