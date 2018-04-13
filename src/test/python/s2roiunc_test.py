#!/usr/bin/env python
# ==========================================            DESCRIPTION            ==========================================

# This script has the goal of


# ===========================================            LIBRARIES            ===========================================
import os
import numpy as np
import datetime
from scipy.misc import imresize
import snappy
import matplotlib

matplotlib.use('Agg')  # this does not show the plot on the screen
import matplotlib.pyplot as pt

# ======================================            CONSTANT VARIABLES            =======================================
# contains the only valid names of the S2 RUT product bands. S2 L1C product bands use same naming excluding "_rut"
S2RUT_BAND_NAMES = ['B1_rut', 'B2_rut', 'B3_rut', 'B4_rut', 'B5_rut', 'B6_rut', 'B7_rut', 'B8_rut', 'B8A_rut',
                    'B11_rut', 'B12_rut']
S2_BAND_CW = [443, 490, 560, 665, 705, 740, 783, 842, 865, 1610, 2190]  # CW for each band
S2RUT_BAND_SAMPLING = [60, 10, 10, 10, 20, 20, 20, 10, 20, 20, 20]  # product before October 2016 is not automatic

ITERPOINTS = 2000  # Number of iteration points that MonteCarlo performs

# append the two folder directories so that can import the classes inside.
ROI_PATH = '/home/data/S2MSI/S2ROI/Gobabeb'  # contains the uncertainty products for each site and stores the results
S2_DATA = '/home/data/S2MSI/Gobabeb'  # here the specified S2 L1C products are read

# It is only prepared to process the *.dim files.
UNC_FILE = "S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644_rut.dim"
ROIUNC_FILE = "S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644_rutroi.dim"
S2FILE = os.path.join("S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644.SAFE", "MTD_MSIL1C.xml")
LAT = -23.6
LON = 15.119
W = 500
H = 500


# =======================================================================================================================

class S2ROIuncprocessor:
    def __init__(self):
        '''
        The class contains all methods and variables necessary to calculate the uncertainty of an ROI mean of S2A.
        The results and study have been integrated in a paper:
        Gorrono, J.; Hunt, S.; Scanlon, T.; Banks, A.; Fox, N.; Woolliams, E.; Underwood, C.; Gascon, F.; Peters,
        M.; Fomferra, N., et al. Providing uncertainty estimates of the sentinel-2 top-of-atmosphere measurements
        for radiometric validation activities. European Journal of Remote Sensing 2017.
        '''
        self.time_init = {'Sentinel-2A': datetime.datetime(2015, 6, 23, 10, 00),
                          'Sentinel-2B': datetime.datetime(2017, 3, 7, 10, 00)}

        self.source_band = None
        self.samp_band = None
        self.roi_uncpixel = []

        self.s2roi = []
        self.wpix = None
        self.hpix = None
        self.x_off = None
        self.y_off = None

        # Values will be obtained from RUT images
        self.unoise = []
        self.uoof_sys = []
        self.uADC = []
        self.uds = []
        self.uL1Cquant = []

        # Value will be obtained from metadata
        self.udifftemp = []
        self.u_diff_temp_rate = {'Sentinel-2A': [0.15, 0.09, 0.04, 0.02, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                                 'Sentinel-2B': [0.15, 0.09, 0.04, 0.02, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}

        # Values taken from https://github.com/senbox-org/snap-rut/blob/master/src/main/python/s2_l1_rad_conf.py (27/06/2017)
        self.uoof_rand = [0.1, 0.1, 0.08, 0.12, 0.44, 0.16, 0.2, 0.2, 0.04, 0, 0]
        self.udiffabs = [1.09, 1.08, 0.84, 0.73, 0.68, 0.97, 0.83, 0.81, 0.88, 1.39, 1.58]  # [%]
        # Values taken from https://github.com/senbox-org/snap-rut/blob/master/src/main/python/s2_rut_algo.py (27/06/2017)
        self.udiffcosine = 0.4  # [%] from 0.13 degrees diffuser planarity
        self.udiffk = 0.3  # [%] as a conservative residual
        self.ugamma = 0.4  # [%]

        self.band_index = None
        self.numrow = None
        self.numcol = None
        self.roi_uncMCM = []

    def selectdeselectmethod(self):
        '''
        Opens the pre-generated uncertainty images and selects the ROI
        Method "select/deselect" as described in article
        Gorrono, J.; Hunt, S.; Scanlon, T.; Banks, A.; Fox, N.; Woolliams, E.; Underwood, C.; Gascon, F.; Peters,
        M.; Fomferra, N., et al. Providing uncertainty estimates of the sentinel-2 top-of-atmosphere measurements
        for radiometric validation activities. European Journal of Remote Sensing 2017.
        '''

        for bandname in S2RUT_BAND_NAMES:
            roiunc_product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, UNC_FILE))
            self.source_band = roiunc_product.getBand(bandname)
            data = self.read_main()
            self.roi_uncpixel.append(data)  # we could add 0.5 or not to account for truncation

            f = pt.figure()
            f.hold(True)
            pt.imshow(data, interpolation='none')
            ax = pt.gca()
            ax.set_title(' S2 TOA unc ' + bandname)
            ax.xaxis.set_label_text('Longitude pixels')
            ax.yaxis.set_label_text('Latitude pixels')

            cbar = pt.colorbar()  # adds the values associated to the colours
            cbar.ax.get_yaxis().labelpad = 15
            cbar.ax.set_ylabel('TOA uncertainty', rotation=270)
            ax.tick_params(axis='both', which='major', labelsize=8)
            ax.tick_params(axis='both', which='minor', labelsize=8)
            ax.invert_yaxis()
            ax.legend(loc='lower left', prop={'size': 10})
            f.savefig(os.path.join(ROI_PATH, 'ROI_' + bandname + '.tif'))
            pt.close(f)

    def MCMmethod(self):
        '''
        Main method that manages the Monte-Carlo approach and compares vs. the select/deselect method.
        :param prod: Sentinel-2 product path that is to be processed
        :return:
        '''
        self.selectdeselectmethod()  # This reads the uncertainty using the RUT

        f, ax = pt.subplots(nrows=3, ncols=1, sharex=True)  # Plot for MCM
        f.hold(True)
        g, ax2 = pt.subplots(nrows=3, ncols=1, sharex=True)  # Plot for MCM vs simple method
        g.hold(True)
        colorlist = ['cyan', 'blue', 'green', 'red', 'orange', 'darkred', 'brown', 'black', 'darkviolet',
                     'magenta', 'darkmagenta']
        for bandname in S2RUT_BAND_NAMES:
            self.samp_band = S2RUT_BAND_SAMPLING[S2RUT_BAND_NAMES.index(bandname)]

            # READ S2ROI
            s2_product = snappy.ProductIO.readProduct(os.path.join(S2_DATA, S2FILE))
            self.source_band = s2_product.getBand(bandname[:-4])  # RUT product same bandname as S2 L1C +_rut
            self.s2roi.append(self.read_main())

            # METHOD 2: calculating the ROI uncertainty from correlation matrices
            # Adds 0.5 to images since they are truncated and the best estimate is 0.5 offset
            product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-7] + 'unoise.dim')
            self.source_band = product.getBand(bandname)
            self.unoise.append(self.read_main() + 0.5)

            product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-7] + 'uoof_sys.dim')
            self.source_band = product.getBand(bandname)
            self.uoof_sys.append(self.read_main() + 0.5)

            product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-7] + 'ADC.dim')
            self.source_band = product.getBand(bandname)
            self.uADC.append(self.read_main() + 0.5)

            product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-7] + 'ds.dim')
            self.source_band = product.getBand(bandname)
            self.uds.append(self.read_main() + 0.5)

            product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-7] + 'uL1Cquant.dim')
            self.source_band = product.getBand(bandname)
            self.uL1Cquant.append(self.read_main() + 0.5)

            metadata_root = s2_product.getMetadataRoot()
            self.udifftemp.append(self.get_u_diff_temp(metadata_root.getElement('Level-1C_DataStrip_ID'),
                                                       S2RUT_BAND_NAMES.index(bandname)))

            self.band_index = S2RUT_BAND_NAMES.index(bandname)
            (self.numrow, self.numcol) = self.s2roi[self.band_index].shape
            roi_uncsamp = self.MCMalgo()

            roi_uncMCM = [np.mean(roi_uncsamp[:, t]) + np.std(roi_uncsamp[:, t]) for t in
                          range(0, roi_uncsamp.shape[1])]
            roi_uncMCM[0] = self.roi_uncpixel[S2RUT_BAND_NAMES.index(bandname)][
                                int(self.numrow / 2), int(
                                    self.numcol / 2)] / 10  # the first is NaN and is replaced by pixel unc/10!!!
            self.roi_uncMCM.append(roi_uncMCM)
            if self.band_index <= 3:  # Visible
                a = ax[0]
                b = ax2[0]
            elif self.band_index >= 9:  # SWIR
                a = ax[2]
                b = ax2[2]
            else:  # case NIR
                a = ax[1]
                b = ax2[1]
            roi_x = [self.samp_band * (1 + 2 * (i - 1)) for i in range(1, roi_uncsamp.shape[1] + 1)]
            a.plot(roi_x, roi_uncMCM,
                   label=bandname[:-4] + ' ' + str(S2_BAND_CW[self.band_index]) + ' nm',
                   color=colorlist[self.band_index], marker='*', linewidth=2)
            b.plot(roi_x, (self.roi_uncpixel[self.band_index] + 0.5) / 10 - roi_uncMCM,
                   label=bandname[:-4] + ' ' + str(S2_BAND_CW[self.band_index]) + ' nm',
                   color=colorlist[self.band_index], marker='*', linewidth=2)
            a.grid(True)
            b.grid(True)
        [a.legend(loc='upper right', ncol=2, numpoints=1, markerscale=1, prop={'size': 10}, fancybox=True) for a in ax]
        f.text(0.5, 0.04, 'ROI size [m]', ha='center')
        f.text(0.04, 0.5, 'Uncertainty $\it{k}$ = 1 [%] (MCM method)', va='center', rotation='vertical')
        [a.set_xlim(a.xaxis.get_data_interval()) for a in ax]
        [a.set_ylim(a.yaxis.get_data_interval()) for a in ax]
        f.savefig(os.path.join(ROI_PATH, 'MCMuncertainty.tif'))
        pt.close(f)
        [b.legend(loc='lower right', numpoints=1, markerscale=1, prop={'size': 10}, fancybox=True) for b in ax2]
        g.text(0.5, 0.04, 'ROI size [m]', ha='center')
        g.text(0.04, 0.5, 'Uncertainty difference $\it{k}$ = 1 [%] (select/deselect vs. MCM)', va='center',
               rotation='vertical')
        [b.set_xlim(b.xaxis.get_data_interval()) for b in ax2]
        [b.set_ylim(b.yaxis.get_data_interval()) for b in ax2]
        g.savefig(os.path.join(ROI_PATH, 'MCMuncertaintydiff.tif'))

    def read_main(self):
        '''
        Convert lat/lon centre coordinates in pixel coordinates of a ROI and extracts values

        :return: Numpy array with selected ROI of the source band
        '''

        # these lines convert centre coordinates LAT, LON in "pix_pos(X,Y)"
        self.wpix = int(round(W / self.samp_band))  # number of pixels in ROI
        self.hpix = int(round(H / self.samp_band))
        geo_pos = snappy.GeoPos()
        geo_pos.lat = LAT
        geo_pos.lon = LON
        pix_pos = snappy.PixelPos()
        geo_code = self.source_band.getGeoCoding()
        geo_code.getPixelPos(geo_pos, pix_pos)

        # upper corner of the ROI need to subtract half the ROI size to pix_pos. Rounded to minimise problem
        self.x_off = int(round(pix_pos.getX() - self.wpix / 2))
        self.y_off = int(round(pix_pos.getY() - self.hpix / 2))

        # with top-coordinates (self.x_off, self.y_off) and size (self.wpix, self.hpix), we can extract the ROI
        roi_data = np.zeros(self.wpix * self.hpix, np.float32)
        self.source_band.readPixels(self.x_off, self.y_off, self.wpix, self.hpix, roi_data)
        roi_data.shape = self.wpix, self.hpix
        return roi_data

    def get_u_diff_temp(self, datastrip_meta, band_id):
        '''
        Calculates an estimation of diffuser degradation based on MERIS diffuser rates
        Minor adaptation of https://github.com/senbox-org/snap-rut/src/main/python/s2_rut.py (accessed on 13/04/2018)

        :param datastrip_meta:
        :param band_id:
        :return:
        '''
        # START or STOP time has no effect. We provide a degradation based on MERIS year rates
        time_start = datetime.datetime.strptime(
            datastrip_meta.getElement('General_Info').getElement('Datastrip_Time_Info').getAttributeString(
                'DATASTRIP_SENSING_START'), '%Y-%m-%dT%H:%M:%S.%fZ')
        return (time_start - self.time_init[self.spacecraft]).days / 365.25 * self.u_diff_temp_rate[self.spacecraft][
            band_id]

    def MCMalgo(self):
        '''
        This is the core of the MonteCarlo ROI uncertainty calculation. The ROI uncertainty for each contributor is
        selected. This is the input to a normal or uniform distribution from which samples are extracted.
        If they are correlated, these samples are extracted from a same distribution and scaled. if uncorrelated the
        samples are extracted once for each pixel independently. It also brings into consideration the option of only
        one dimension is correlated. This is obtained by a for loop at each row/ column.
        The ROI samples are
        :return:  array with ITERPOINTS samples as rows and different ROI size as columns
        '''
        hf = int(self.numrow / 2)  # finds the half width of the ROI

        # Calculate results of the MCM method
        roi_uncsamp = []
        for j in range(0, ITERPOINTS):
            roi_uncsize = []
            # print "Iteration: " + str(j)

            # ROI OF ERRORS: Each 'uxxx' represent errors out of the distribution (uncertainty) at each iteration
            # Divide by 10 uncertainty image since is multiplied by that number
            unoise = np.empty_like(self.s2roi[self.band_index])
            unoise[:] = np.random.normal(0, self.unoise[self.band_index], (self.numrow, self.numcol)) / 10

            uoof_rand = np.ones_like(self.s2roi[self.band_index]) * self.uoof_rand[self.band_index]
            for row in range(0, self.numrow):
                uoof_rand[row, :] = np.random.normal(0, uoof_rand[row, :] + 1e-9, self.numcol)  # avoids 0 std

            uADC = np.empty_like(self.s2roi[self.band_index])
            uADC[:] = np.random.uniform(-self.uADC[self.band_index] * np.sqrt(3),
                                        self.uADC[self.band_index] * np.sqrt(3), (self.numrow, self.numcol)) / 10

            udiffabs = np.ones_like(self.s2roi[self.band_index]) * self.udiffabs[self.band_index]
            udiffabs[:] = np.random.normal(0, 1, 1)[0] * udiffabs

            udiffcosine = np.ones_like(self.s2roi[self.band_index]) * self.udiffcosine
            udiffcosine[:] = np.random.normal(0, 1, 1)[0] * udiffcosine

            udiffk = np.ones_like(self.s2roi[self.band_index]) * self.udiffk
            udiffk[:] = np.random.normal(0, 1, 1)[0] * udiffk

            uds = np.empty_like(self.s2roi[self.band_index])
            uds[:] = np.random.uniform(-1, 1, 1)[0] * self.uds[self.band_index] * np.sqrt(3) / 10

            ugamma = np.empty_like(self.s2roi[self.band_index])
            for row in range(0, self.numrow):
                ugamma[row, :] = np.random.normal(0, self.ugamma, self.numcol)

            uL1Cquant = np.empty_like(self.s2roi[self.band_index])
            uL1Cquant[:] = np.random.uniform(-self.uL1Cquant[self.band_index] * np.sqrt(3),
                                             self.uL1Cquant[self.band_index] * np.sqrt(3),
                                             (self.numrow, self.numcol)) / 10

            # Combination of all error samples
            # The errors of the distribution must be multiplied by S2 TOA reflectance pixels (s2ref)
            # and normalise to the mean of these.
            for d in range(0, hf + 1):  # d represents at each iteration the pixels from the centre 1x1, 3x3, 5x5
                s2ref = self.s2roi[self.band_index][hf - d:hf + d, hf - d:hf + d]
                oof_sys = np.mean(self.uoof_sys[self.band_index][hf - d:hf + d, hf - d:hf + d] / 10 * s2ref) / np.mean(
                    s2ref)
                sys = oof_sys + self.udifftemp[self.band_index]
                standardunc = np.mean(
                    (unoise[hf - d:hf + d, hf - d:hf + d] + uoof_rand[hf - d:hf + d, hf - d:hf + d] +
                     uADC[hf - d:hf + d, hf - d:hf + d] + udiffabs[hf - d:hf + d, hf - d:hf + d] +
                     udiffcosine[hf - d:hf + d, hf - d:hf + d] + udiffk[hf - d:hf + d, hf - d:hf + d] +
                     uds[hf - d:hf + d, hf - d:hf + d] + ugamma[hf - d:hf + d, hf - d:hf + d] +
                     uL1Cquant[hf - d:hf + d, hf - d:hf + d]) * s2ref) / np.mean(s2ref)
                roi_uncsize.append(sys + standardunc)

            roi_uncsamp.append(roi_uncsize)

        return np.array(roi_uncsamp)
