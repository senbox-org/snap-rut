# -*- coding: utf-8 -*-
"""
Created on Wed Jan 20 13:48:33 2016

@author: jg9
"""
import snappy
from snappy import HashMap as hash
import s2_rut_algo
import numpy as np
import datetime
import os

try:
    import xml.etree.cElementTree as ET  # C implementation is much faster and consumes significantly less memory
except ImportError:
    import xml.etree.ElementTree as ET
import s2_l1_rad_conf as rad_conf

# necessary for logging
# from snappy import SystemUtils

S2_MSI_TYPE_STRING = 'S2_MSI_Level-1C'
S2_BAND_NAMES = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B9', 'B10', 'B11', 'B12']
S2_BAND_SAMPLING = {'B1': 60, 'B2': 10, 'B3': 10, 'B4': 10, 'B5': 20, 'B6': 20, 'B7': 20, 'B8': 10, 'B8A': 20, 'B9': 60,
                    'B10': 60, 'B11': 20, 'B12': 20}

# If a Java type is needed which is not imported by snappy by default it can be retrieved manually.
# First import jpy and then the type to be imported
from snappy import jpy

MetadataElement = jpy.get_type('org.esa.snap.core.datamodel.MetadataElement')
MetadataAttribute = jpy.get_type('org.esa.snap.core.datamodel.MetadataAttribute')


class S2RutOp:
    def __init__(self):
        self.s2_rut_info = None
        self.source_product = None
        self.mask_group = None
        self.product_meta = None
        self.datastrip_meta = None
        self.spacecraft = None  # possible values are "Sentinel-2A" and "Sentinel-2B". Used as a dictionary key
        self.rut_algo = s2_rut_algo.S2RutAlgo()
        self.unc_band = None
        self.toa_band = None
        # S2A launch date 23-june-2015 and S2A launch date 7-march-2017, time is indifferent.
        self.time_init = {'Sentinel-2A': datetime.datetime(2015, 6, 23, 10, 00),
                          'Sentinel-2B': datetime.datetime(2017, 3, 7, 10, 00)}
        self.sourceBandMap = None
        self.targetBandList = []
        self.inforoot = None
        self.rut_product_meta = None
        self.source_sza = None

    def initialize(self, context):
        self.source_product = context.getSourceProduct()

        if self.source_product.getProductType() != S2_MSI_TYPE_STRING:
            raise RuntimeError('Source product must be of type "' + S2_MSI_TYPE_STRING + '"')

        self.mask_group = self.source_product.getMaskGroup()  # obtain the masks from the product
        metadata_root = self.source_product.getMetadataRoot()
        self.product_meta = metadata_root.getElement('Level-1C_User_Product')
        self.datastrip_meta = metadata_root.getElement('Level-1C_DataStrip_ID')
        granules_meta = metadata_root.getElement('Granules')

        self.spacecraft = self.datastrip_meta.getElement('General_Info').getElement('Datatake_Info').getAttributeString(
            'SPACECRAFT_NAME')

        # todo - check if there is a granule

        self.toa_band_names = context.getParameter('band_names')
        if not self.toa_band_names:
            raise RuntimeError(
                'No S2 bands were selected. Please select the S2 bands from the "Processing parameters" tab')

        self.rut_algo.u_sun = self.get_u_sun(self.product_meta)
        self.rut_algo.quant = self.get_quant(self.product_meta)
        # tecta = 0.0
        # for granule_meta in granules_meta.getElements():
        #     tecta += self.get_tecta(granule_meta)
        # self.rut_algo.tecta = tecta / granules_meta.getNumElements()
        self.source_sza = self.get_tecta()
        self.rut_algo.k = self.get_k(context)
        self.rut_algo.unc_select = self.get_unc_select(context)

        self.sourceBandMap = {}
        for name in self.toa_band_names:
            # TODO - Change the interface so that undesired bands (e.g azimuth) are not shown.
            if not name in S2_BAND_NAMES:  # The band name is checked to confirm it is valid band.
                if ('view_' in name) or ('sun_' in name):
                    continue  # the angular bands are shown in the GUI and we simply jump to the next band if selected
                else:
                    raise RuntimeError('Source band "' + name + '" is not valid and has not been processed')

            source_band = self.source_product.getBand(name)
            unc_toa_band = snappy.Band(name + '_rut', snappy.ProductData.TYPE_UINT8, source_band.getRasterWidth(),
                                       source_band.getRasterHeight())
            unc_toa_band.setDescription('Uncertainty of ' + name + ' (coverage factor k=' + str(self.rut_algo.k) + ')')
            unc_toa_band.setNoDataValue(250)
            unc_toa_band.setNoDataValueUsed(True)
            self.targetBandList.append(unc_toa_band)
            self.sourceBandMap[unc_toa_band] = source_band
            snappy.ProductUtils.copyGeoCoding(source_band, unc_toa_band)

        masterband = self.get_masterband(self.targetBandList)
        rut_product = snappy.Product(self.source_product.getName() + '_rut', 'S2_RUT',
                                     masterband.getRasterWidth(), masterband.getRasterHeight())  # in-memory product
        snappy.ProductUtils.copyGeoCoding(masterband, rut_product)
        for band in self.targetBandList:
            rut_product.addBand(band)

        # The metadata from the RUT product is defined
        self.rut_product_meta = rut_product.getMetadataRoot()  # Here we define the product metadata
        # SOURCE_PRODUCT
        sourceelem = MetadataElement('Source_product')
        data = snappy.ProductData.createInstance(self.source_product.getDisplayName())
        sourceattr = MetadataAttribute("SOURCE_PRODUCT", snappy.ProductData.TYPE_ASCII, data.getNumElems())
        sourceattr.setData(data)
        sourceelem.addAttribute(sourceattr)
        self.rut_product_meta.addElement(sourceelem)
        # COVERAGE_FACTOR
        sourceelem = MetadataElement('Coverage_factor')
        data = snappy.ProductData.createInstance(str(context.getParameter('coverage_factor')))
        sourceattr = MetadataAttribute("COVERAGE_FACTOR", snappy.ProductData.TYPE_ASCII, data.getNumElems())
        sourceattr.setData(data)
        sourceelem.addAttribute(sourceattr)
        self.rut_product_meta.addElement(sourceelem)
        # RUT_VERSION
        version = context.getSpi().getOperatorDescriptor().getVersion() # returns what written in the *-info.xml file
        sourceelem = MetadataElement('Version')
        data = snappy.ProductData.createInstance(version)
        sourceattr = MetadataAttribute("VERSION", snappy.ProductData.TYPE_ASCII, data.getNumElems())
        sourceattr.setData(data)
        sourceelem.addAttribute(sourceattr)
        self.rut_product_meta.addElement(sourceelem)
        # CONTRIBUTOR LIST: List of selected ones
        sourceelem = MetadataElement('List_Contributors')
        contributors = ["INSTRUMENT_NOISE", "OOF_STRAYLIGHT-SYSTEMATIC", "OOF_STRAYLIGHT-RANDOM", "CROSSTALK",
                        "ADC_QUANTISATION", "DS_STABILITY", "GAMMA_KNOWLEDGE", "DIFFUSER-ABSOLUTE_KNOWLEDGE",
                        "DIFFUSER-TEMPORAL_KNOWLEDGE", "DIFFUSER-COSINE_EFFECT", "DIFFUSER-STRAYLIGHT_RESIDUAL",
                        "L1C_IMAGE_QUANTISATION"]
        for i in range(0, len(contributors)):
            data = snappy.ProductData.createInstance(str(self.rut_algo.unc_select[i]))
            sourceattr = MetadataAttribute(contributors[i], snappy.ProductData.TYPE_ASCII, data.getNumElems())
            sourceattr.setData(data)
            sourceelem.addAttribute(sourceattr)
        self.rut_product_meta.addElement(sourceelem)
        # DATE OF PROCESSING
        sourceelem = MetadataElement('Processing_datetime')
        data = snappy.ProductData.createInstance(str(datetime.datetime.now()))
        sourceattr = MetadataAttribute("PROCESSING_DATETIME", snappy.ProductData.TYPE_ASCII, data.getNumElems())
        sourceattr.setData(data)
        sourceelem.addAttribute(sourceattr)
        self.rut_product_meta.addElement(sourceelem)

        context.setTargetProduct(rut_product)

    def computeTile(self, context, band, tile):
        # Logging template
        # SystemUtils.LOG.info('target band name: ' + band.getName())
        # SystemUtils.LOG.info('tile rect: ' + tile.getRectangle().toString())

        source_band = self.sourceBandMap[band]
        toa_band_id = np.int(S2_BAND_NAMES.index(source_band.getName()))

        if S2_BAND_SAMPLING[source_band.getName()] == 10:  # selects the correct resampled SZA band
            source_sza = self.source_sza[0]
            cloudmask = self.mask_roi('opaque_clouds_10m', tile.getRectangle())
            cirrusmask = self.mask_roi('cirrus_clouds_10m', tile.getRectangle())
        elif S2_BAND_SAMPLING[source_band.getName()] == 20:
            source_sza = self.source_sza[1]
            cloudmask = self.mask_roi('opaque_clouds_20m', tile.getRectangle())
            cirrusmask = self.mask_roi('cirrus_clouds_20m', tile.getRectangle())
        elif S2_BAND_SAMPLING[source_band.getName()] == 60:
            source_sza = self.source_sza[2]
            cloudmask = self.mask_roi('opaque_clouds_60m', tile.getRectangle())
            cirrusmask = self.mask_roi('cirrus_clouds_60m', tile.getRectangle())

        sza_tile = context.getSourceTile(source_sza, tile.getRectangle())  # selects the tile SZA values
        sza_samples = sza_tile.getSamplesFloat()
        self.rut_algo.tecta = sza_samples

        self.rut_algo.a = self.get_a(self.datastrip_meta, toa_band_id)
        self.rut_algo.e_sun = self.get_e_sun(self.product_meta, toa_band_id)
        self.rut_algo.alpha = self.get_alpha(self.datastrip_meta, toa_band_id)
        self.rut_algo.beta = self.get_beta(self.datastrip_meta, toa_band_id)
        self.rut_algo.u_diff_temp = self.get_u_diff_temp(self.datastrip_meta, toa_band_id)

        toa_tile = context.getSourceTile(source_band, tile.getRectangle())
        toa_samples = toa_tile.getSamplesFloat()

        # this is the core where the uncertainty calculation should grow
        unc = self.rut_algo.unc_calculation(np.array(toa_samples, dtype=np.float64), toa_band_id, self.spacecraft)

        degrademask = self.mask_roi('msi_degraded_' + source_band.getName(), tile.getRectangle())
        lostmask = self.mask_roi('msi_lost_' + source_band.getName(), tile.getRectangle())
        defectmask = self.mask_roi('defective_' + source_band.getName(), tile.getRectangle())
        invalidmask = np.maximum(np.maximum(degrademask, lostmask), defectmask)
        satl1amask = self.mask_roi('saturated_l1a_' + source_band.getName(), tile.getRectangle())
        satl1bmask = self.mask_roi('saturated_l1b_' + source_band.getName(), tile.getRectangle())
        satl1mask = np.maximum(satl1amask, satl1bmask)
        nodatamask = self.mask_roi('nodata_' + source_band.getName(), tile.getRectangle())
        # selects the maximum element-wise. Mask true value is 255. This is higher than 250 (max uncertainty permitted)
        # 251 is for degraded,lost or defective data. 252 is for saturated (L1a or L1b). 253 is for pixel with no data,
        # 254 is for cirrus cloud and 255 is for opaque clouds.
        val = np.maximum(unc, np.uint8(251 * invalidmask / 255))
        val = np.maximum(val, np.uint8(252 * satl1mask / 255))
        val = np.maximum(val, np.uint8(253 * nodatamask / 255))
        val = np.maximum(val, np.uint8(254 * cirrusmask / 255))
        val = np.maximum(val, np.uint8(cloudmask))
        tile.setSamples(val)

    # NOTE: this is a function that it is not stable enough
    # def computeTileStack(self, context, target_tiles, target_rectangle):
    #     for targetband in self.targetBandList:
    #         source_band = self.sourceBandMap[targetband]
    #         tile = target_tiles.get(targetband)  # target_tiles is a Map<Band,Tile>
    #         toa_band_id = np.int(S2_BAND_NAMES.index(source_band.getName()))
    #         self.rut_algo.a = self.get_a(self.datastrip_meta, toa_band_id)
    #         self.rut_algo.e_sun = self.get_e_sun(self.product_meta, toa_band_id)
    #         self.rut_algo.alpha = self.get_alpha(self.datastrip_meta, toa_band_id)
    #         self.rut_algo.beta = self.get_beta(self.datastrip_meta, toa_band_id)
    #         self.rut_algo.u_diff_temp = self.get_u_diff_temp(self.datastrip_meta, toa_band_id)
    #
    #         toa_tile = context.getSourceTile(source_band, snappy.Rectangle(source_band.getRasterWidth(),
    #                                                                        source_band.getRasterHeight()))
    #         toa_samples = toa_tile.getSamplesFloat()
    #
    #         # this is the core where the uncertainty calculation should grow
    #         unc = self.rut_algo.unc_calculation(np.array(toa_samples, dtype=np.float64), toa_band_id, self.spacecraft)
    #
    #         tile.setSamples(unc)

    def dispose(self, context):
        pass

    def get_quant(self, product_meta):
        return (product_meta.getElement('General_info').getElement('Product_Image_Characteristics').
                getAttributeDouble('QUANTIFICATION_VALUE'))

    def get_u_sun(self, product_meta):
        return (product_meta.getElement('General_Info').getElement('Product_Image_Characteristics').
                getElement('Reflectance_Conversion').getAttributeDouble('U'))

    # def get_tecta(self, granule_meta):
    #     '''
    #     Deprecated function. Used for S2-RUTv1
    #     :param granule_meta:
    #     :return:
    #     '''
    #     return (granule_meta.getElement('Geometric_info').getElement('Tile_Angles').getElement('Mean_Sun_Angle').
    #             getAttributeDouble('ZENITH_ANGLE'))

    def get_tecta(self):
        '''
        Generates the SZA resampled at the S2 bands spatial resolution
        :return: SZA angle bands resampled at 10,20 and 60m.
        '''
        parameters = hash()
        parameters.put('targetResolution', 20)
        parameters.put('upsampling', 'Bilinear')
        parameters.put('downsampling', 'Mean')  # indiferent since angles will be always upsampled
        parameters.put('flagDownsampling', 'FlagMedianAnd')
        parameters.put('resampleOnPyramidLevels', True)
        product20 = snappy.GPF.createProduct('Resample', parameters, self.source_product)
        parameters.put('targetResolution', 10)
        product10 = snappy.GPF.createProduct('Resample', parameters, self.source_product)
        parameters.put('targetResolution', 60)
        product60 = snappy.GPF.createProduct('Resample', parameters, self.source_product)
        return (product10.getBand('sun_zenith'), product20.getBand('sun_zenith'), product60.getBand('sun_zenith'))

    def get_e_sun(self, product_meta, band_id):
        return float([i for i in product_meta.getElement('General_Info').getElement('Product_Image_Characteristics').
                     getElement('Reflectance_Conversion').getElement('Solar_Irradiance_list').
                     getAttributes() if i.getName() == 'SOLAR_IRRADIANCE'][band_id].getData().getElemString())

    def get_u_diff_temp(self, datastrip_meta, band_id):
        # START or STOP time has no effect. We provide a degradation based on MERIS year rates
        time_start = datetime.datetime.strptime(datastrip_meta.getElement('General_Info').
            getElement('Datastrip_Time_Info').getAttributeString(
            'DATASTRIP_SENSING_START'), '%Y-%m-%dT%H:%M:%S.%fZ')
        return (time_start - self.time_init[self.spacecraft]).days / 365.25 * \
               rad_conf.u_diff_temp_rate[self.spacecraft][band_id]

    def get_beta(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').getElements() if i.getName() == 'Radiometric_Quality'][band_id]
                .getElement('Noise_Model').getAttributeDouble('BETA'))

    def get_alpha(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.getElement('Quality_Indicators_Info').getElement('Radiometric_Info').
                getElement('Radiometric_Quality_list').getElements() if i.getName() == 'Radiometric_Quality'][band_id]
                .getElement('Noise_Model').getAttributeDouble('ALPHA'))

    def get_a(self, datastrip_meta, band_id):
        return ([i for i in datastrip_meta.getElement('Image_Data_Info').getElement('Sensor_Configuration').
                getElement('Acquisition_Configuration').getElement('Spectral_Band_Info').getElements()
                 if i.getName() == 'Spectral_Band_Information'][band_id].getAttributeDouble('PHYSICAL_GAINS'))

    def get_k(self, context):
        return (context.getParameter('coverage_factor'))

    def get_unc_select(self, context):
        return ([context.getParameter('Instrument_noise'), context.getParameter('OOF_straylight-systematic'),
                 context.getParameter('OOF_straylight-random'), context.getParameter('Crosstalk'),
                 context.getParameter('ADC_quantisation'), context.getParameter('DS_stability'),
                 context.getParameter('Gamma_knowledge'), context.getParameter('Diffuser-absolute_knowledge'),
                 context.getParameter('Diffuser-temporal_knowledge'), context.getParameter('Diffuser-cosine_effect'),
                 context.getParameter('Diffuser-straylight_residual'), context.getParameter('L1C_image_quantisation')])

    def get_masterband(self, targetBandList):
        max_width = -1
        band_index = -1
        for index, band in enumerate(targetBandList):
            width = band.getRasterWidth()
            if width > max_width:
                band_index = index
                max_width = width
        return targetBandList[band_index]

    def mask_roi(self, masktag, rectangle):
        '''
        The function supports the automatic read of ROI masks in function masks_extract
        :param masktag: the tag of the mask from the S2 L1C product (list of them in self.source_product.getBandNames())
        :return: ROI of raster data from the specific mask in integer (0 or 1 value)
        '''
        data = np.zeros(rectangle.width * rectangle.height, np.uint32)
        im = self.mask_group.get(masktag)
        im2 = snappy.jpy.cast(im, snappy.Mask)  # change from ProductNode to Mask typo
        im2.readPixels(rectangle.x, rectangle.y, rectangle.width, rectangle.height, data)
        # No need to reshape data as unc values are not!!!
        # data.shape = rectangle.height, rectangle.width
        return data
