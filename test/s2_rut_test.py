import unittest
import s2_rut
import snappy


class S2RutOpTest(unittest.TestCase):
    def test_simple_case(self):

        var = s2_rut.S2RutOp()
        var.bandId = 7
        var.tileId = snappy.ProductIO.readProduct(
            'D:\s2_products\S2A_OPER_PRD_MSIL1C_PDMC_20160112T203346_R051_V20160112T110648_20160112T110648.SAFE\GRANULE\S2A_OPER_MSI_L1C_TL_SGS__20160112T162938_A002908_T31TCE_N02.01\S2A_OPER_MTD_L1C_TL_SGS__20160112T162938_A002908_T31TCE.xml')
        result = var._unc_calculation([100, 500, 1000, 2000, 5000, 10000, 15000])

        self.assertEqual([225, 54, 32, 22, 16, 13, 13], result)
