# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 13:48:33 2016

@author: jg9
"""

import numpy as np
import math

import s2_l1_rad_conf as rad_conf


class S2RutAlgo:
    """
    Algorithm for the Sentinel-2 Radiometric Uncertainty Tool (RUT)
    """

    def __init__(self):
        # uncertainty values for DS and Abs.cal
        self.a = 0.0
        self.e_sun = 0.0
        self.u_sun = 1.0
        self.tecta = 0.0
        self.quant = 10000.0
        self.alpha = 0.0
        self.beta = 0.0
        self.u_diff_cos = 0.4  # [%]from 0.13° diffuser planarity/micro as in (AIRBUS 2015)
        self.u_diff_k = 0.3  # [%] as a conservative residual (AIRBUS 2015)
        self.u_diff_temp = 1.0  # [%] as a conservative residual (AIRBUS 2015)
        self.u_ADC = 0.5  # [DN](rectangular distribution, see combination)
        self.k = 1

    def unc_calculation(self, band_data, band_id):
        """
        This function represents the core of the RUTv1.
        It takes as an input the pixel data of a specific band and tile in
        a S2-L1C product and produces an image with the same dimensions that
        contains the radiometric uncertainty of each pixel reflectance factor.

        The steps and its numbering is equivalent to the RUT-DPM. This document
        can be found in the tool github. Also there a more detailed explanation
        of the theoretical background can be found.

        :param band_data: list with the quantized L1C reflectance pixels of a band (flattened; 1-d)
        :param band_id: zero-based index of the band
        :return: list of u_int8 with uncertainty associated to each pixel.
        """

        #######################################################################        
        # 1.	Initial check
        #######################################################################        
        # a.	Cloud pixel
        # b.	pixel_value == 0, [product metadata] General_Info/Product_Image_Characteristics/Special_Values/SPECIAL_VALUE_TEXT [NODATA]
        # c.	pixel_value == 1,  [product metadata] General_Info/Product_Image_Characteristics/Special_Values/SPECIAL_VALUE_TEXT [SATURATED]


        #######################################################################
        # 2.	Undo reflectance conversion
        #######################################################################
        # a.	No action required
        # b.	[product metadata] #issue: missing one band
        #    General_Info/Product_Image_Characteristics/PHYSICAL_GAINS [bandId]
        #    [datastrip metadata]
        #    Image_Data_Info/Sensor_Configuration/Acquisition_Configuration/
        #    Spectral_Band_Info/Spectral_Band_Information [bandId]/ PHYSICAL_GAINS                
        if self.tecta > 70 and not self.tecta_warning:  # (see RUT DPM DISCUSSION for explanation and alternative)
            self.tecta_warning = True
            print('Tile mean SZA is' + str(self.tecta) + '-->conversion error >5%')

        # Replace the reflectance factors by CN values (avoid memory duplicate)
        band_data[:] = [i * self.a * self.e_sun * self.u_sun * math.cos(math.radians(self.tecta)) /
                        (math.pi * self.quant) for i in band_data]

        #######################################################################
        # 3.	Orthorectification process
        #######################################################################        
        # TBD in RUTv2. Here both terms will be used with no distinction.

        #######################################################################        
        # 4.	L1B uncertainty contributors: raw and dark signal
        #######################################################################

        # u_noise is directly added in the combination see section 8

        # [W.m-2.sr-1.μm-1] 0.3%*Lref all bands (AIRBUS 2015) and (AIRBUS 2014)
        u_stray_sys = 0.3 * rad_conf.Lref[band_id] / 100

        u_stray_rand = rad_conf.u_stray_rand_all[band_id]  # [%](AIRBUS 2015) and (AIRBUS 2012)

        u_xtalk = rad_conf.u_xtalk_all[band_id]  # [W.m-2.sr-1.μm-1](AIRBUS 2015)

        u_DS = rad_conf.u_DS_all[band_id]

        #######################################################################        
        # 5.	L1B uncertainty contributors: gamma correction
        #######################################################################        

        u_gamma = 0.4  # [%] (AIRBUS 2015)

        #######################################################################        
        # 6.	L1C uncertainty contributors: absolute calibration coefficient
        #######################################################################

        u_diff_abs = rad_conf.u_diff_absarray[band_id]

        #######################################################################
        # 7.	L1C uncertainty contributors: reflectance conversion
        #######################################################################

        u_ref_quant = 100 * (0.5 / self.quant)  # [%]scaling 0-1 in steps number=quant

        #######################################################################        
        # 8.	Combine uncertainty contributors
        #######################################################################        
        # NOTE: no gamma propagation for RUTv1!!!
        # values given as percentages. Multiplied by 10 and saved to 1 byte(uint8)
        # Clips values to 0-250 --> uncertainty >=25%  assigns a value 250.
        # Uncertainty <=0 represents a processing error (uncertainty is positive)
        u_ref = []
        for cn in band_data:
            u_noise = 100 * math.sqrt(self.alpha ** 2 + self.beta * cn) / cn
            u_adc = 100 * self.u_ADC / math.sqrt(3) / cn
            u_ds = 100 * u_DS / cn
            u_stray = math.sqrt(u_stray_rand ** 2 + (100 * self.a * u_xtalk / cn) ** 2)
            u_diff = math.sqrt(u_diff_abs ** 2 + self.u_diff_cos ** 2 + self.u_diff_k ** 2)
            u_1sigma = math.sqrt((u_ref_quant / math.sqrt(3)) ** 2 + u_gamma ** 2 + u_stray ** 2 + u_diff ** 2 +
                                 u_noise ** 2 + u_adc ** 2 + u_ds ** 2)
            u_expand = 10 * (self.u_diff_temp + (100 * self.a * u_stray_sys / cn) + self.k * u_1sigma)
            u_ref.append(np.uint8(np.clip(u_expand, 0, 250)))

        #######################################################################        
        # 9.	Append uncertainty information to the metadata
        #######################################################################         
        # Here the metadata relevant to the uncertainty image created is added
        # Rad_uncertainty_info [BandId]--> Mean, std. dev, median and
        # quantile_info_list[5% steps]

        # granule_meta.addElement()

        return u_ref
