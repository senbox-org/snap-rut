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

import sys  # we need to define the location of the main code to get some of its data

sys.path.append(os.path.join(os.getcwd(), 'src', 'main', 'python'))
import s2_l1_rad_conf as rad_conf
import s2_rut

s2rutop = s2_rut.S2RutOp()
import s2_rut_algo

s2rutalgo = s2_rut_algo.S2RutAlgo()

# ======================================            CONSTANT VARIABLES            =======================================
# contains the only valid names of the S2 RUT product bands. S2 L1C product bands use same naming excluding "_rut"
S2RUT_BAND_NAMES = ['B1_rut', 'B2_rut', 'B3_rut', 'B4_rut', 'B5_rut', 'B6_rut', 'B7_rut', 'B8_rut', 'B8A_rut', 'B9_rut',
                    'B10_rut', 'B11_rut', 'B12_rut']
S2RUT_BAND_SAMPLING = {'B1_rut': 60, 'B2_rut': 10, 'B3_rut': 10, 'B4_rut': 10, 'B5_rut': 20, 'B6_rut': 20, 'B7_rut': 20,
                       'B8_rut': 10, 'B8A_rut': 20, 'B9_rut': 60, 'B10_rut': 60, 'B11_rut': 20, 'B12_rut': 20}

ITERPOINTS = 2000  # Number of iteration points that MonteCarlo performs

# append the two folder directories so that can import the classes inside.
ROI_PATH = '/home/data/satellite/S2A_MSI/S2ROI/Gobabeb'  # contains the uncertainty products for each site and stores the results
S2_DATA = '/home/data/satellite/S2A_MSI/L1/RadCalNet/GONA'  # here the specified S2 L1C products are read

# It is only prepared to process the *.dim files.
UNC_FILE = "S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644_rut.dim"
ROIUNC_FILE = "S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644_rutroibc.dim"
S2FILE = os.path.join("S2A_MSIL1C_20170609T084601_N0205_R107_T33KWP_20170609T090644.SAFE", "MTD_MSIL1C.xml")
LAT = -23.6
LON = 15.119
# In order to work, the ROI width and height must be the same.
W = 500
H = 500


# =======================================================================================================================

class S2ROIuncprocessor:
    def __init__(self):
        '''
        The class contains all methods and variables necessary to calculate the uncertainty of an ROI mean of S2.
        The results and study have been integrated in a paper:
        Gorrono, J.; Hunt, S.; Scanlon, T.; Banks, A.; Fox, N.; Woolliams, E.; Underwood, C.; Gascon, F.; Peters,
        M.; Fomferra, N., et al. Providing uncertainty estimates of the sentinel-2 top-of-atmosphere measurements
        for radiometric validation activities. European Journal of Remote Sensing 2017.
        '''
        self.spacecraft = None
        self.datastrip_meta = None
        self.bandnames = None
        self.source_band = None
        self.roi_uncpixel = []  # ROI pixels with the systematic uncertainty contributions only selected.
        self.uncpixel = []  # ROI pixels with the specific per pixel uncertainty (all contributions included).
        self.s2roi = []  # TOA reflectance factor values in the Region of Interest

        # These values will be obtained from RUT images in MCMmethod() and read in function MCMalgo()
        self.unoise = None
        self.u_stray_sys = None
        self.uADC = None
        self.uds = None
        self.uL1Cquant = None

        # Value will be obtained from metadata in get_u_diff_temp()
        self.udifftemp = None

        # Values taken from s2_l1_rad_conf.py
        self.u_stray_rand = None
        self.udiffabs = None

        # Values taken from s2_rut_algo.py. These are fix values.
        self.udiffcosine = s2rutalgo.u_diff_cos
        self.udiffk = s2rutalgo.u_diff_k
        self.ugamma = s2rutalgo.u_gamma

        self.roi_uncMCM = []  # brings all the uncertainty results for the MonteCarlo Method

    def MCMmethod(self):
        '''
        Main method that manages the Monte-Carlo approach and compares vs. the select/deselect method.
        :param prod: Sentinel-2 product path that is to be processed
        :return:
        '''
        roiunc_product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE))
        unc_product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, UNC_FILE))
        self.bandnames = [i for i in roiunc_product.getBandNames()]
        try:
            self.bandnames == [i for i in unc_product.getBandNames()]
        except:
            raise RuntimeError(
                'Mismatch bands between uncertainty products. All the uncertainty products must have the same bands')

        s2_product = snappy.ProductIO.readProduct(os.path.join(S2_DATA, S2FILE))
        metadata_root = s2_product.getMetadataRoot()
        self.datastrip_meta = metadata_root.getElement('Level-1C_DataStrip_ID')
        self.spacecraft = self.datastrip_meta.getElement('General_Info').getElement('Datatake_Info').getAttributeString(
            'SPACECRAFT_NAME')

        f, ax = pt.subplots(nrows=3, ncols=1, sharex=True)  # Plot for MCM
        f.hold(True)
        g, ax2 = pt.subplots(nrows=3, ncols=1, sharex=True)  # Plot for MCM vs simple method
        g.hold(True)
        colorlist = ['cyan', 'blue', 'green', 'red', 'orange', 'darkred', 'brown', 'black', 'darkviolet', 'aqua',
                     'sienna', 'magenta', 'darkmagenta']
        for bandname in self.bandnames:
            self.source_band = roiunc_product.getBand(bandname)
            dataroi = self.read_main(S2RUT_BAND_SAMPLING[bandname])
            self.roi_uncpixel.append(dataroi)  # we could add 0.5 or not to account for truncation

            self.source_band = unc_product.getBand(bandname)
            datapixel = self.read_main(S2RUT_BAND_SAMPLING[bandname])
            self.uncpixel.append(datapixel)  # we could add 0.5 or not to account for truncation

            self.plot_ROI(datapixel, dataroi, bandname)

            # READ S2ROI
            self.source_band = s2_product.getBand(bandname[:-4])  # RUT product same bandname as S2 L1C +_rut
            self.s2roi = self.read_main(S2RUT_BAND_SAMPLING[bandname])
            band_index = S2RUT_BAND_NAMES.index(bandname)

            self.unoise = self.get_unc_image('unoise',bandname)
            self.u_stray_sys = self.get_unc_image('u_stray_sys',bandname)
            self.uADC = self.get_unc_image('ADC',bandname)
            self.uds = self.get_unc_image('ds',bandname)
            self.uL1Cquant = self.get_unc_image('uL1Cquant',bandname)

            self.udifftemp = self.get_u_diff_temp(self.datastrip_meta, band_index)
            self.udiffabs = rad_conf.u_diff_absarray[self.spacecraft][band_index]
            self.u_stray_rand = rad_conf.u_stray_rand_all[self.spacecraft][band_index]

            roi_uncsamp = self.MCMalgo()

            roi_uncMCM = [np.mean(roi_uncsamp[:, t]) + np.std(roi_uncsamp[:, t]) for t in
                          range(0, roi_uncsamp.shape[1])]
            roi_uncMCM[0] = np.mean(datapixel) / 10  # the first is replaced by pixel unc/10!!!
            self.roi_uncMCM.append(roi_uncMCM)
            if band_index <= 3:  # Visible
                a = ax[0]
                b = ax2[0]
            elif band_index >= 9:  # SWIR
                a = ax[2]
                b = ax2[2]
            else:  # case NIR
                a = ax[1]
                b = ax2[1]
            roi_x = [S2RUT_BAND_SAMPLING[bandname] * (1 + 2 * (i - 1)) for i in range(1, roi_uncsamp.shape[1] + 1)]
            a.plot(roi_x, roi_uncMCM, label=bandname[:-4], color=colorlist[band_index], marker='*', linewidth=2)
            b.plot(roi_x, np.mean(dataroi) / 10 - roi_uncMCM, label=bandname[:-4],
                   color=colorlist[band_index], marker='*', linewidth=2)
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

    def read_main(self, sampling):
        '''
        Convert lat/lon centre coordinates in pixel coordinates of a ROI and extracts values
        :sampling: Spatial sampling in meters from the S2 band.
        :return: Numpy array with selected ROI of the source band
        '''

        # these lines convert centre coordinates LAT, LON in "pix_pos(X,Y)"
        wpix = int(round(W / sampling))  # number of pixels in ROI
        hpix = int(round(H / sampling))
        geo_pos = snappy.GeoPos()
        geo_pos.lat = LAT
        geo_pos.lon = LON
        pix_pos = snappy.PixelPos()
        geo_code = self.source_band.getGeoCoding()
        geo_code.getPixelPos(geo_pos, pix_pos)

        # upper corner of the ROI need to subtract half the ROI size to pix_pos. Rounded to minimise problem
        x_off = int(round(pix_pos.getX() - wpix / 2))
        y_off = int(round(pix_pos.getY() - hpix / 2))

        # with top-coordinates (self.x_off, self.y_off) and size (self.wpix, self.hpix), we can extract the ROI
        roi_data = np.zeros(wpix * hpix, np.float32)
        self.source_band.readPixels(x_off, y_off, wpix, hpix, roi_data)
        roi_data.shape = wpix, hpix
        return roi_data

    def get_u_diff_temp(self, datastrip_meta, band_id):
        '''
        Calculates an estimation of diffuser degradation based on MERIS diffuser rates
        Minor adaptation of s2_rut.py (accessed on 13/04/2018)
        :param datastrip_meta:
        :param band_id:
        :return:
        '''
        # START or STOP time has no effect. We provide a degradation based on MERIS year rates
        time_start = datetime.datetime.strptime(
            datastrip_meta.getElement('General_Info').getElement('Datastrip_Time_Info').getAttributeString(
                'DATASTRIP_SENSING_START'), '%Y-%m-%dT%H:%M:%S.%fZ')
        return (time_start - s2rutop.time_init[self.spacecraft]).days / 365.25 * \
               rad_conf.u_diff_temp_rate[self.spacecraft][band_id]

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
        (numrow, numcol) = self.s2roi.shape
        hf = int(numrow / 2)  # finds the half width of the ROI

        # Calculate results of the MCM method
        roi_uncsamp = []
        for j in range(0, ITERPOINTS):
            roi_uncsize = []
            # print "Iteration: " + str(j)

            # ROI OF ERRORS: Each 'uxxx' represent errors out of the distribution (uncertainty) at each iteration
            # Divide by 10 uncertainty image since is multiplied by that number
            unoise = np.empty_like(self.s2roi)
            unoise[:] = np.random.normal(0, self.unoise, (numrow, numcol)) / 10

            u_stray_rand = np.ones_like(self.s2roi) * self.u_stray_rand
            for row in range(0, numrow):
                u_stray_rand[row, :] = np.random.normal(0, u_stray_rand[row, :] + 1e-9, numcol)  # avoids 0 std

            uADC = np.empty_like(self.s2roi)
            uADC[:] = np.random.uniform(-self.uADC * np.sqrt(3), self.uADC * np.sqrt(3), (numrow, numcol)) / 10

            udiffabs = np.ones_like(self.s2roi) * self.udiffabs
            udiffabs[:] = np.random.normal(0, 1, 1)[0] * udiffabs

            udiffcosine = np.ones_like(self.s2roi) * self.udiffcosine
            udiffcosine[:] = np.random.normal(0, 1, 1)[0] * udiffcosine

            udiffk = np.ones_like(self.s2roi) * self.udiffk
            udiffk[:] = np.random.normal(0, 1, 1)[0] * udiffk

            uds = np.empty_like(self.s2roi)
            uds[:] = np.random.uniform(-1, 1, 1)[0] * self.uds * np.sqrt(3) / 10

            ugamma = np.empty_like(self.s2roi)
            for row in range(0, numrow):
                ugamma[row, :] = np.random.normal(0, self.ugamma, numcol)

            uL1Cquant = np.empty_like(self.s2roi)
            uL1Cquant[:] = np.random.uniform(-self.uL1Cquant * np.sqrt(3), self.uL1Cquant * np.sqrt(3),
                                             (numrow, numcol)) / 10

            # Combination of all error samples
            # The errors of the distribution must be multiplied by S2 TOA reflectance pixels (s2ref)
            # and normalise to the mean of these.
            for d in range(0, hf + 1):  # d represents at each iteration the pixels from the centre 1x1, 3x3, 5x5
                s2ref = self.s2roi[hf - d:hf + d, hf - d:hf + d]
                u_stray_sys = np.mean(self.u_stray_sys[hf - d:hf + d, hf - d:hf + d] / 10 * s2ref) / np.mean(s2ref)
                sys = u_stray_sys + self.udifftemp
                standardunc = np.mean(
                    (unoise[hf - d:hf + d, hf - d:hf + d] + u_stray_rand[hf - d:hf + d, hf - d:hf + d] +
                     uADC[hf - d:hf + d, hf - d:hf + d] + udiffabs[hf - d:hf + d, hf - d:hf + d] +
                     udiffcosine[hf - d:hf + d, hf - d:hf + d] + udiffk[hf - d:hf + d, hf - d:hf + d] +
                     uds[hf - d:hf + d, hf - d:hf + d] + ugamma[hf - d:hf + d, hf - d:hf + d] +
                     uL1Cquant[hf - d:hf + d, hf - d:hf + d]) * s2ref) / np.mean(s2ref)
                roi_uncsize.append(sys + standardunc)

            roi_uncsamp.append(roi_uncsize)

        return np.array(roi_uncsamp)

    def plot_ROI(self, datapixel, dataroi, bandname):
        '''
        Plots the ROI pixels for uncertainty with all contributors and with correlated ones only selected.
        :param datapixel: pixel with full uncertainty
        :param dataROI: pixels with pre-selected systematic correlated uncertainty
        :param bandname: string with name of the band
        :return:
        '''
        f = pt.figure()
        f.hold(True)
        pt.imshow(dataroi, interpolation='none')
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

        f = pt.figure()
        f.hold(True)
        pt.imshow(datapixel, interpolation='none')
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
        f.savefig(os.path.join(ROI_PATH, 'Pixelunc_' + bandname + '.tif'))
        pt.close(f)

    def get_unc_image(self,tagname, bandname):
        '''
        Retieves the ROI uncertainty for the specific contributor image generated.
        :param tagname: tag phrase for the uncertainty product
        :param bandname: string with the name of the band
        :return: ROI uncertainty values for that contributor and band
        '''
        product = snappy.ProductIO.readProduct(os.path.join(ROI_PATH, ROIUNC_FILE)[:-9] + tagname + '.dim')
        self.source_band = product.getBand(bandname)
        return self.read_main(S2RUT_BAND_SAMPLING[bandname])