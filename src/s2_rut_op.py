# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 13:48:33 2016

@author: jg9
"""
import snappy
import s2_rut_algo


class S2RutOp:

    def __init__(self):
        self.source_product = None
        self.product_meta = None
        self.datastrip_meta = None
        self.rut_algo = s2_rut_algo.S2RutAlgo()
        self.unc_band = None
        self.unc_flags_band = None

    def initialize(self, context):
        self.source_product = context.getSourceProduct('source')

        # todo - validate source_product

        self.product_meta, self.datastrip_meta, granules_meta = self.source_product.getMetadataRoot().getElements()
        granule_meta = [i for i in granules_meta.getElements()][0]

        self.rut_algo.u_sun = self.get_u_sun(self.product_meta)
        self.rut_algo.quant = self.get_quant(self.product_meta)
        self.rut_algo.tecta = self.get_tecta(granule_meta)

        scene_width = self.source_product.getSceneRasterWidth()
        scene_height = self.source_product.getSceneRasterHeight()

        rut_product = snappy.Product(self.source_product.getName() + '_rut', 'S2_RUT', scene_width, scene_height)
        self.unc_band = rut_product.addBand('unc', snappy.ProductData.TYPE_UINT8)
        self.unc_flags_band = rut_product.addBand('unc_flags', snappy.ProductData.TYPE_UINT8)
    
        context.setTargetProduct(rut_product)


    def compute(self, context, target_tiles, target_rectangle):
        # todo - iterate over source bands and get the index
        band_names = self.source_product.getBandNames()
        band_index = 7
        self.rut_algo.a = self.get_a(self.datastrip_meta, band_index)
        self.rut_algo.e_sun = self.get_e_sun(self.product_meta, band_index)
        self.rut_algo.alpha = self.get_alpha(self.datastrip_meta, band_index)
        self.rut_algo.beta = self.get_beta(self.datastrip_meta, band_index)
        self.rut_algo.u_diff_temp = self.get_u_diff_temp(self.datastrip_meta, band_index)

        toa_tile = context.getSourceTile(self.toa_band, target_rectangle)
    
        unc_tile = target_tiles.get(self.unc_band)
        unc_flags_tile = target_tiles.get(self.unc_flags_band)
    
        toa_samples = toa_tile.getSamplesFloat()
        # this is the core where the uncertainty calculation should grow
        unc = self._unc_calculation(toa_samples)
    
        unc_tile.setSamples(unc)
        #unc_flags_tile.setSamples(unc_flags)
    
    
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
    
    def get_tecta(self, granule_meta):
        return (granule_meta.getElement('Geometric_info').
                getElement('Tile_Angles').getElement('Mean_Sun_Angle').
                getAttributeDouble('ZENITH_ANGLE'))


    def get_e_sun(self, product_meta, band_id):
        return float([i for i in product_meta.getElement('General_Info').
                     getElement('Product_Image_Characteristics').
                     getElement('Reflectance_Conversion').
                     getElement('Solar_Irradiance_list').getAttributes() if i.getName() ==
                      'SOLAR_IRRADIANCE'][band_id].getData().getElemString())
    
    def get_u_diff_temp(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.
                getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').getElements()
                 if i.getName() == 'Radiometric_Quality'][band_id]
                .getAttributeDouble('MULTI_TEMPORAL_CALIBRATION_ACCURACY'))

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
    