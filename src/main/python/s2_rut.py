# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 13:48:33 2016

@author: jg9
"""
import snappy
import s2_rut_algo
import numpy as np
import datetime
import s2_l1_rad_conf as rad_conf

SUN_AZIMUTH_BAND_NAME = "sun_azimuth"
S2_MSI_TYPE_STRING = 'S2_MSI_Level-1C'


class S2RutOp:
    def __init__(self):
        self.source_product = None
        self.product_meta = None
        self.datastrip_meta = None
        self.rut_algo = s2_rut_algo.S2RutAlgo()
        self.unc_band = None
        self.toa_band = None
        self.time_init = datetime.datetime(2015, 6, 23, 10, 00)  # S2A launch date 23-june-2015, time is indifferent
        self.target_source_map = None

    def initialize(self, context):
        self.source_product = context.getSourceProduct()

        if self.source_product.getProductType() != S2_MSI_TYPE_STRING:
            raise RuntimeError('Source product must be of type "' + S2_MSI_TYPE_STRING + '"')

        self.product_meta, self.datastrip_meta = self.source_product.getMetadataRoot().getElements()

        self.toa_band_names = context.getParameter('band_names')

        self.rut_algo.u_sun = self.get_u_sun(self.product_meta)
        self.rut_algo.quant = self.get_quant(self.product_meta)
        self.rut_algo.k = self.get_k(context)
        self.rut_algo.unc_select = self.get_unc_select(context)

        scene_width = self.source_product.getSceneRasterWidth()
        scene_height = self.source_product.getSceneRasterHeight()

        rut_product = snappy.Product(self.source_product.getName() + '_rut', 'S2_RUT', scene_width, scene_height)
        snappy.ProductUtils.copyGeoCoding(self.source_product, rut_product)
        self.target_source_map = {}
        for name in self.toa_band_names:
            source_band = self.source_product.getBand(name)
            unc_toa_band = snappy.Band(name + '_rut', snappy.ProductData.TYPE_UINT8, source_band.getRasterWidth(),
                                       source_band.getRasterHeight())
            unc_toa_band.setDescription('Uncertainty of ' + name + ' (coverage factor k=' + str(self.rut_algo.k) + ')')
            unc_toa_band.setNoDataValue(250)
            unc_toa_band.setNoDataValueUsed(True)
            rut_product.addBand(unc_toa_band)
            self.target_source_map[unc_toa_band] = source_band
            snappy.ProductUtils.copyGeoCoding(source_band, unc_toa_band)

        context.setTargetProduct(rut_product)

    def computeTile(self, context, target_band, tile):
        source_band = self.target_source_map[target_band]
        toa_band_id = source_band.getSpectralBandIndex() - 1
        self.rut_algo.a = self.get_a(self.datastrip_meta, toa_band_id)
        self.rut_algo.e_sun = self.get_e_sun(self.product_meta, toa_band_id)
        self.rut_algo.alpha = self.get_alpha(self.datastrip_meta, toa_band_id)
        self.rut_algo.beta = self.get_beta(self.datastrip_meta, toa_band_id)
        self.rut_algo.u_diff_temp = self.get_u_diff_temp(self.datastrip_meta, toa_band_id)

        toa_tile = context.getSourceTile(source_band, tile.getRectangle())
        toa_samples = toa_tile.getSamplesInt()
        sun_azimuth_tile = context.getSourceTile(self.source_product.getBand(SUN_AZIMUTH_BAND_NAME), tile.getRectangle())
        sun_azimuth_samples = sun_azimuth_tile.getSamplesFloat()

        # this is the core where the uncertainty calculation should grow
        unc = self.rut_algo.unc_calculation(toa_band_id, np.array(toa_samples, dtype=np.uint16),
                                            np.array(sun_azimuth_samples, dtype=np.float32))

        tile.setSamples(unc)

    def dispose(self, context):
        pass

    def get_quant(self, product_meta):
        return (product_meta.getElement('General_info').
                getElement('Product_Image_Characteristics').
                getAttributeDouble('QUANTIFICATION_VALUE'))

    def get_u_sun(self, product_meta):
        return (product_meta.getElement('General_Info').
                getElement('Product_Image_Characteristics').
                getElement('Reflectance_Conversion').getAttributeDouble('U'))

    def get_e_sun(self, product_meta, band_id):
        return float([i for i in product_meta.getElement('General_Info').
                     getElement('Product_Image_Characteristics').
                     getElement('Reflectance_Conversion').
                     getElement('Solar_Irradiance_list').getAttributes() if i.getName() ==
                      'SOLAR_IRRADIANCE'][band_id].getData().getElemString())

    def get_u_diff_temp(self, datastrip_meta, band_id):
        # START or STOP time has no effect. We provide a degradation based on MERIS year rates
        time_start = datetime.datetime.strptime(datastrip_meta.getElement('General_Info').
                                                getElement('Datastrip_Time_Info').
                                                getAttributeString('DATASTRIP_SENSING_START'), '%Y-%m-%dT%H:%M:%S.%fZ')
        return (time_start - self.time_init).days / 365.25 * rad_conf.u_diff_temp_rate[band_id]

    def get_beta(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.
                getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').
                getElements() if i.getName() == 'Radiometric_Quality'][band_id]
                .getElement('Noise_Model').getAttributeDouble('BETA'))

    def get_alpha(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.
                getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').
                getElements() if i.getName() == 'Radiometric_Quality'][band_id]
                .getElement('Noise_Model').getAttributeDouble('ALPHA'))

    def get_a(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.getElement('Image_Data_Info').
                getElement('Sensor_Configuration').
                getElement('Acquisition_Configuration').
                getElement('Spectral_Band_Info').getElements()
                 if i.getName() == 'Spectral_Band_Information'][band_id]
                .getAttributeDouble('PHYSICAL_GAINS'))

    def get_k(self, context):
        return (context.getParameter('coverage_factor'))

    def get_unc_select(self, context):
        return ([context.getParameter('Instrument_noise'), context.getParameter('OOF_straylight-systematic'),
                 context.getParameter('OOF_straylight-random'), context.getParameter('Crosstalk'),
                 context.getParameter('ADC_quantisation'), context.getParameter('DS_stability'),
                 context.getParameter('Gamma_knowledge'), context.getParameter('Diffuser-absolute_knowledge'),
                 context.getParameter('Diffuser-temporal_knowledge'), context.getParameter('Diffuser-cosine_effect'),
                 context.getParameter('Diffuser-straylight_residual'), context.getParameter('L1C_image_quantisation')])
