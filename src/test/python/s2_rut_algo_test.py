import unittest
import s2_rut_algo as s2_rut_algo
import numpy as np


class S2RutAlgoTest(unittest.TestCase):
    def test_simple_case_B8(self):
        rut_algo = s2_rut_algo.S2RutAlgo()
        rut_algo.a = 6.22865527455779
        rut_algo.e_sun = 1036.39
        rut_algo.u_sun = 1.03418574554466
        rut_algo.quant = 10000.0
        rut_algo.alpha = 0.571
        rut_algo.beta = 0.04447
        rut_algo.u_ADC = 0.5

        band_data = [100, 500, 1000, 2000, 5000, 10000, 15000.]
        sun_asimuth = np.empty(7)
        sun_asimuth.fill(63.5552301619033)

        rut_result = rut_algo.unc_calculation(7, np.array(band_data), sun_asimuth)

        self.assertEqual([250, 85, 55, 39, 28, 24, 23], list(rut_result))

    def test_simple_case_B2(self):
        rut_algo = s2_rut_algo.S2RutAlgo()
        rut_algo.a = 6.22865527455779
        rut_algo.e_sun = 1036.39
        rut_algo.u_sun = 1.03418574554466
        rut_algo.tecta = 63.5552301619033
        rut_algo.quant = 10000.0
        rut_algo.alpha = 0.571
        rut_algo.beta = 0.04447
        rut_algo.u_ADC = 0.5

        band_data = [100, 500, 1000, 2000, 5000, 10000, 15000.]
        sun_asimuth = np.empty(7)
        sun_asimuth.fill(63.5552301619033)

        rut_result = rut_algo.unc_calculation(1, np.array(band_data), sun_asimuth)

        self.assertEqual([250, 96, 61, 42, 31, 26, 25], list(rut_result))

    def test_simple_case_B1(self):
        rut_algo = s2_rut_algo.S2RutAlgo()
        rut_algo.a = 6.22865527455779
        rut_algo.e_sun = 1036.39
        rut_algo.u_sun = 1.03418574554466
        rut_algo.quant = 10000.0
        rut_algo.alpha = 0.571
        rut_algo.beta = 0.04447
        rut_algo.u_ADC = 0.5

        sun_asimuth = np.empty(7)
        sun_asimuth.fill(63.5552301619033)

        band_data = [100, 500, 1000, 2000, 5000, 10000, 15000.]
        rut_result = rut_algo.unc_calculation(0, np.array(band_data), sun_asimuth)

        self.assertEqual([250, 97, 61, 42, 31, 26, 25], list(rut_result))


