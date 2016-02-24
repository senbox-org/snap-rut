# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 13:48:33 2016

@author: jg9
"""
import snappy
import numpy
import math


class S2RutOp:
    def __init__(self):
        # jpy = snappy.jpy
        # jpy.diag.flags = jpy.diag.F_ALL
        self.toa_band = None
        self.tileId = None
        self.unc_band = None
        self.unc_flags_band = None
        self.bandId = None
        self.u_ds = 0.0
        self.u_a = 0.0

    def initialize(self, context):
        source_product = context.getSourceProduct('source')

        print('initialize: source product location is',
              source_product.getFileLocation())


        # gets the uncertainty values for DS and Abs.cal
        self.u_ds = context.getParameter('ds_unc')
        self.u_a = context.getParameter('cal_unc')

        # gets the B1 of the product. This will be made iterative for all bands
        band = context.getParameter('toa_band')
        if not band:
            raise RuntimeError('Missing parameter "toa_band"')
        self.toa_band = self._get_band(source_product, band)

        # NOTE: I do not create a new product but include new bands on the source
        # This creates a new product without any reader (in-memory product)        
        unc_product = snappy.Product('py_unc', 'py_unc', width, height)
        self.unc_band = unc_product.addBand('unc', snappy.ProductData.TYPE_UINT8)
        self.unc_flags_band = unc_product.addBand('unc_flags',
                                                  snappy.ProductData.TYPE_UINT8)

        context.setTargetProduct(unc_product)

    def compute(self, context, target_tiles, target_rectangle):

        # For the RUTv1 we will read a whole tile of a specific band

        toa_tile = context.getSourceTile(self.toa_band, target_rectangle)

        unc_tile = target_tiles.get(self.unc_band)
        unc_flags_tile = target_tiles.get(self.unc_flags_band)

        toa_samples = toa_tile.getSamplesFloat()
        # this is the core where the uncertainty calculation should grow
        unc = self._unc_calculation(toa_samples)

        unc_tile.setSamples(unc)
        unc_flags_tile.setSamples(unc_flags)

    def dispose(self, context):
        pass

    def _get_band(self, product, name):
        band = product.getBand(name)
        if not band:
            raise RuntimeError('Product does not contain a band named', name)
        return band

    def _unc_calculation(self, tile_data):
        '''
        This function represents the core of the RUTv1.
        It takes as an input the pixel data of a specific band and tile in 
        a S2-L1C product and produces an image with the same dimensions that 
        contains the radiometric uncertainty of each pixel reflectance factor.
        
        The steps and its numbering is equivalent to the RUT-DPM. This document
        can be found in the tool github. Also there a more detailed explanation
        of the theoretical background can be found.
        
        INPUT:
        tile_data: list with the pixels one tile of a band (flattened; 1-d)
        OUTPUT:
        u_ref: list of u_int8 with uncetainty associated to each pixel.
        
        '''
        #######################################################################        
        # 1.	Initial check
        #######################################################################        
        # a.	Cloud pixel
        # b.	pixel_value == 0, [product metadata] General_Info/Product_Image_Characteristics/Special_Values/SPECIAL_VALUE_TEXT [NODATA]
        # c.	pixel_value == 1,  [product metadata] General_Info/Product_Image_Characteristics/Special_Values/SPECIAL_VALUE_TEXT [SATURATED]
        # d. Obtain metadata pointers

        # ['Level-1C_User_Product', 'Level-1C_DataStrip_ID', 'Granules']        
        product_meta, datastrip_meta, granules_meta = self.tileId. \
            getMetadataRoot().getElements()

        # the pointer is to one granule and there should be only one granule
        # e.g.snappy.ProductIO.readProduct('D:\s2_products\S2A_OPER_PRD_MSIL1C_
        # PDMC_20160112T203346_R051_V20160112T110648_20160112T110648.SAFE\
        # GRANULE\S2A_OPER_MSI_L1C_TL_SGS__20160112T162938_A002908_T31TCE_N02.01
        # \S2A_OPER_MTD_L1C_TL_SGS__20160112T162938_A002908_T31TCE.xml')

        granule_meta = [i for i in granules_meta.getElements()][0]

        #######################################################################
        # 2.	Undo reflectance conversion
        #######################################################################
        # a.	No action required
        # b.	[product metadata] #issue: missing one band
        #    General_Info/Product_Image_Characteristics/PHYSICAL_GAINS [bandId]
        #    [datastrip metadata]
        #    Image_Data_Info/Sensor_Configuration/Acquisition_Configuration/
        #    Spectral_Band_Info/Spectral_Band_Information [bandId]/ PHYSICAL_GAINS                

        a = ([i for i in datastrip_meta.getElement('Image_Data_Info').
             getElement('Sensor_Configuration').
             getElement('Acquisition_Configuration').
             getElement('Spectral_Band_Info').getElements()
              if i.getName() == 'Spectral_Band_Information'][self.bandId]
             .getAttributeDouble('PHYSICAL_GAINS'))
        print('a =', a)

        # c.	[product metadata] General_Info/Product_Image_Characteristics/
        #   Reflectance_Conversion/Solar_Irradiance_list/SOLAR_IRRADIANCE[bandId]
        # NOTE: all the attributes in XML are text, do not use getElemFloat
        e_sun = float([i for i in product_meta.getElement('General_Info').
                      getElement('Product_Image_Characteristics').
                      getElement('Reflectance_Conversion').
                      getElement('Solar_Irradiance_list').getAttributes() if i.getName() ==
                       'SOLAR_IRRADIANCE'][self.bandId].getData().getElemString())

        # d.	[product metadata] General_Info/Product_Image_Characteristics/Reflectance_Conversion/U
        u_sun = (product_meta.getElement('General_Info').
                 getElement('Product_Image_Characteristics').
                 getElement('Reflectance_Conversion').getAttributeDouble('U'))
        # e.	[tile metadata] Geometric_info/Tile_Angles/Mean_Sun_Angle/ZENITH_ANGLE
        tecta = (granule_meta.getElement('Geometric_info').
                 getElement('Tile_Angles').getElement('Mean_Sun_Angle').
                 getAttributeDouble('ZENITH_ANGLE'))
        if tecta > 70:  # (see RUT DPM DISCUSSION for explanation and alternative)
            print('Tile mean SZA is' + str(tecta) + '-->conversion error >5%')

        # f.	[product metadata] #scaling to 0-1 range (can be higher)
        #    General_Info/Product_Image_Characteristics/QUANTIFICATION_VALUE
        quant = (product_meta.getElement('General_info').
                 getElement('Product_Image_Characteristics').
                 getAttributeDouble('QUANTIFICATION_VALUE'))

        # Replace the reflectance factors by CN values (avoid memory duplicate)
        tile_data[:] = [i * a * e_sun * u_sun * math.cos(math.radians(tecta)) /
                        (math.pi * quant) for i in tile_data]

        #######################################################################
        # 3.	Orthorectification process
        #######################################################################        
        # TBD in RUTv2. Here both terms will be used with no distinction.

        #######################################################################        
        # 4.	L1B uncertainty contributors: raw and dark signal
        #######################################################################

        # [datastrip metadata]Quality_Indicators_Info/Radiometric_Info/
        # Radiometric_Quality_list/Radiometric_Quality [bandId]/Noise_Model/ALPHA
        alpha = ([i for i in datastrip_meta.
                 getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                 getElement('Radiometric_Quality_list').
                 getElements() if i.getName() == 'Radiometric_Quality'][self.bandId]
                 .getElement('Noise_Model').getAttributeDouble('ALPHA'))

        beta = ([i for i in datastrip_meta.
                getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').
                getElements() if i.getName() == 'Radiometric_Quality'][self.bandId]
                .getElement('Noise_Model').getAttributeDouble('BETA'))

        # u_noise is directly added in the combination see section 8

        Lref = [129.11, 128, 128, 108, 74.6, 68.23, 66.70, 103, 52.39, 8.77, 6, 4, 1.70]
        # [W.m-2.sr-1.μm-1] 0.3%*Lref all bands (AIRBUS 2015) and (AIRBUS 2014)
        u_stray_sys = 0.3 * Lref[self.bandId] / 100

        u_stray_rand_all = [0.1, 0.1, 0.08, 0.12, 0.44, 0.16, 0.2, 0.2, 0.04, 0.8, 0, 0, 0]
        u_stray_rand = u_stray_rand_all[self.bandId]  # [%](AIRBUS 2015) and (AIRBUS 2012)

        u_xtalk_all = [0.05, 0.01, 0.01, 0.01, 0.04, 0.03, 0.04, 0.02, 0.03, 0.02, 0.19,
                       0.15, 0.02]

        u_xtalk = u_xtalk_all[self.bandId]  # [W.m-2.sr-1.μm-1](AIRBUS 2015)

        u_ADC = 0.5  # [DN](rectangular distribution, see combination)

        u_DS_all = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.24, 0.12, 0.16]
        u_DS = u_DS_all[self.bandId]

        #######################################################################        
        # 5.	L1B uncertainty contributors: gamma correction
        #######################################################################        

        u_gamma = 0.4  # [%] (AIRBUS 2015)

        #######################################################################        
        # 6.	L1C uncertainty contributors: absolute calibration coefficient
        #######################################################################

        u_diff_absarray = [1.09, 1.08, 0.84, 0.73, 0.68, 0.97, 0.83, 0.81, 0.88, 0.97,
                           1.39, 1.39, 1.58]  # [%] values in  (AIRBUS 2015)
        u_diff_abs = u_diff_absarray[self.bandId]

        # [datastrip metadata] Quality_Indicators_Info/Radiometric_Info/
        # Radiometric_Quality_list/Radiometric_Quality [bandId]/
        # MULTI_TEMPORAL_CALIBRATION_ACCURACY
        u_diff_temp = ([i for i in datastrip_meta.
                       getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                       getElement('Radiometric_Quality_list').getElements()
                        if i.getName() == 'Radiometric_Quality'][self.bandId]
                       .getAttributeDouble('MULTI_TEMPORAL_CALIBRATION_ACCURACY'))

        u_diff_cos = 0.4  # [%]from 0.13° diffuser planarity/micro as in (AIRBUS 2015)

        u_diff_k = 0.3  # [%] as a conservative residual (AIRBUS 2015)

        #######################################################################
        # 7.	L1C uncertainty contributors: reflectance conversion
        #######################################################################

        u_ref_quant = 100 * (0.5 / quant)  # [%]scaling 0-1 in steps number=quant

        #######################################################################        
        # 8.	Combine uncertainty contributors
        #######################################################################        
        # NOTE: no gamma propagation for RUTv1!!!        
        # u_noise = [math.sqrt(alpha**2 + beta*cn) for cn in tile_data] #[DN]
        # u_ADC_bis = [100*u_ADC/math.sqrt(3)/cn for cn in tile_data]
        # u_DS_bis = [100*u_DS/cn for cn in tile_data]
        # u_LSB = [math.sqrt((100*u_noise/cn)**2 + u_ADC_bis**2 +
        #        u_DS_bis**2) for cn in tile_data]
        # u_stray = [math.sqrt(u_stray_rand**2 + (100*a/cn)**2*(u_stray_sys**2
        #            + u_xtalk**2)) for cn in tile_data]
        # u_diff = math.sqrt(u_diff_abs**2 + (u_diff_temp/math.sqrt(3))**2 +
        #            u_diff_cos**2 + u_diff_k**2)
        # u_ref = math.sqrt((u_ref_quant/math.sqrt(3))**2 + u_gamma**2 +
        #            u_stray**2 + u_diff**2 + u_LSB**2)

        # All in one line to avoid serial execution (memory duplication)
        # values given as percentages. Multiplied by 10 and saved to 1 byte(uint8)
        # Clips values to 0-250 --> uncertainty >=25%  assigns a value 250.
        # Uncertainty <=0 represents a processing error (uncertainty is positive)
        u_ref = [numpy.uint8(numpy.clip(10 * math.sqrt((u_ref_quant / math.sqrt(3)) ** 2
                                                       + u_gamma ** 2 + u_stray_rand ** 2 + (100 * a / cn) ** 2 * (
                                                       u_stray_sys ** 2 +
                                                       u_xtalk ** 2) + u_diff_abs ** 2 + (
                                                       u_diff_temp / math.sqrt(3)) ** 2 +
                                                       u_diff_cos ** 2 + u_diff_k ** 2 + (
                                                       100 * math.sqrt(alpha ** 2 + beta * cn) / cn) ** 2
                                                       + (100 * u_ADC / math.sqrt(3) / cn) ** 2 + (
                                                       100 * u_DS / cn) ** 2)), 0, 250)
                 for cn in tile_data]

        #        print(u_ref_quant,u_gamma,u_stray_rand,(100*a*u_stray_sys/cn)**2,
        #               (100*a*u_xtalk/cn)**2,u_diff_abs,u_diff_temp,u_diff_cos,u_diff_k,
        #                100*math.sqrt(alpha**2 + beta*cn)/cn,math.sqrt(alpha**2 + beta*cn),
        #                100*u_ADC/math.sqrt(3)/cn,u_ADC,100*u_DS/cn,u_DS)
        #
        #        print tile_data[0]/a

        #######################################################################        
        # 9.	Append uncertainty information to the metadata
        #######################################################################         
        # Here the metadata relevant to the uncertainty image created is added
        # Rad_uncertainty_info [BandId]--> Mean, std. dev, median and
        # quantile_info_list[5% steps]

        # granule_meta.addElement()

        return u_ref


var = S2RutOp()
