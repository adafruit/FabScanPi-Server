from __future__ import division
from builtins import str
from builtins import zip
from builtins import range
from builtins import object
from past.utils import old_div
__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

import math
import logging, os
import numpy as np
import scipy.ndimage
import cv2
from fabscan.FSConfig import ConfigInterface
from fabscan.FSSettings import SettingsInterface
from fabscan.lib.util.FSInject import inject
from fabscan.scanner.interfaces.FSImageProcessor import ImageProcessorInterface


class LinearLeastSquares2D(object):
    '''
    2D linear least squares using the hesse normal form:
        d = x*sin(theta) + y*cos(theta)
    which allows you to have vertical lines.
    '''

    def fit(self, data):
        data_mean = data.mean(axis=0)
        x0, y0 = data_mean
        if data.shape[0] > 2:  # over determined
            u, v, w = np.linalg.svd(data - data_mean)
            vec = w[0]
            theta = math.atan2(vec[0], vec[1])
        elif data.shape[0] == 2:  # well determined
            theta = math.atan2(data[1, 0] - data[0, 0], data[1, 1] - data[0, 1])
        theta = (theta + old_div(math.pi * 5, 2)) % (2 * math.pi)
        d = x0 * math.sin(theta) + y0 * math.cos(theta)
        return d, theta

    def residuals(self, model, data):
        d, theta = model
        dfit = data[:, 0] * math.sin(theta) + data[:, 1] * math.cos(theta)
        return np.abs(d - dfit)

    def is_degenerate(self, sample):
        return False


@inject(
    config=ConfigInterface,
    settings=SettingsInterface
)
class ImageProcessor(ImageProcessorInterface):
    def __init__(self, config, settings):

        self.settings = settings
        self.config = config
        self._logger = logging.getLogger(__name__)
        self.red_channel = 'R (RGB)'
        self.threshold_enable = False
        self.threshold_value = 0
        self.blur_enable = False
        self.blur_value = 0
        self.window_enable = False
        self.window_value = 0
        self.color = (255, 255, 255)
        self.refinement_method = 'SGF' #possible  RANSAC, SGF
        self.image_height = self.config.camera.resolution.width
        self.image_width = self.config.camera.resolution.height
        self._weight_matrix = self._compute_weight_matrix()
        self._criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        self.object_pattern_points = self.create_object_pattern_points()

    def init(self, resolution):
        self.image_height = resolution[0]
        self.image_width = resolution[1]
        self._weight_matrix = self._compute_weight_matrix()

    def _compute_weight_matrix(self):
        _weight_matrix = np.array(
            (np.matrix(np.linspace(0, self.image_width - 1, self.image_width)).T *
             np.matrix(np.ones(self.image_height))).T)
        return _weight_matrix

    def create_object_pattern_points(self):
        objp = np.zeros((self.config.calibration.pattern.rows * self.config.calibration.pattern.columns, 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.config.calibration.pattern.columns,
                      0:self.config.calibration.pattern.rows].T.reshape(-1, 2)
        objp = np.multiply(objp, self.config.calibration.pattern.square_size)
        return objp

    def ransac(self, data, model_class, min_samples, threshold, max_trials=100):
        '''
        Fits a model to data with the RANSAC algorithm.
        :param data: numpy.ndarray
            data set to which the model is fitted, must be of shape NxD where
            N is the number of data points and D the dimensionality of the data
        :param model_class: object
            object with the following methods implemented:
             * fit(data): return the computed model
             * residuals(model, data): return residuals for each data point
             * is_degenerate(sample): return boolean value if sample choice is
                degenerate
            see LinearLeastSquares2D class for a sample implementation
        :param min_samples: int
            the minimum number of data points to fit a model
        :param threshold: int or float
            maximum distance for a data point to count as an inlier
        :param max_trials: int, optional
            maximum number of iterations for random sample selection, default 100
        :returns: tuple
            best model returned by model_class.fit, best inlier indices
        '''

        best_model = None
        best_inlier_num = 0
        best_inliers = None
        data_idx = np.arange(data.shape[0])
        for _ in range(max_trials):
            sample = data[np.random.randint(0, data.shape[0], 2)]
            if model_class.is_degenerate(sample):
                continue
            sample_model = model_class.fit(sample)
            sample_model_residua = model_class.residuals(sample_model, data)
            sample_model_inliers = data_idx[sample_model_residua < threshold]
            inlier_num = sample_model_inliers.shape[0]
            if inlier_num > best_inlier_num:
                best_inlier_num = inlier_num
                best_inliers = sample_model_inliers
        if best_inliers is not None:
            best_model = model_class.fit(data[best_inliers])
        return best_model

    def _window_mask(self, image, window_enable=True):

        window_value = 3
        mask = 0
        if window_enable:
            peak = image.argmax(axis=1)
            _min = peak - window_value
            _max = peak + window_value + 1
            mask = np.zeros_like(image)
            for i in range(self.image_height):
                mask[i, _min[i]:_max[i]] = 255
                # Apply mask
        image = cv2.bitwise_and(image, mask)

        return image

    def _threshold_image(self, image, blur_enable=True):

        image = cv2.threshold(
            image, self.settings.threshold, 255, cv2.THRESH_TOZERO)[1]

        if blur_enable:
            image = cv2.blur(image, (5, 5))

        image = cv2.threshold(
            image, self.settings.threshold, 255, cv2.THRESH_TOZERO)[1]

        return image

    def _obtain_red_channel(self, image):
        ret = None
        if self.red_channel == 'R (RGB)':
            ret = cv2.split(image)[0]
        elif self.red_channel == 'Cr (YCrCb)':
            ret = cv2.split(cv2.cvtColor(image, cv2.COLOR_RGB2YCR_CB))[1]
        elif self.red_channel == 'U (YUV)':
            ret = cv2.split(cv2.cvtColor(image, cv2.COLOR_RGB2YUV))[1]
        return ret

    def compute_line_segmentation(self, image, roi_mask=False):
        if image is not None:
            if roi_mask is True:
                image = self.mask_image(image)
            image = self._obtain_red_channel(image)
            if image is not None:
                # Threshold image
                image = self._threshold_image(image)
                # Window mask
                image = self._window_mask(image)

            return image

    def _sgf(self, u, v, s):
        if len(u) > 1:
            i = 0
            sigma = 2.0
            f = np.array([])
            segments = [s[_r] for _r in np.ma.clump_unmasked(np.ma.masked_equal(s, 0))]
            # Detect stripe segments
            for segment in segments:
                j = len(segment)
                # Apply gaussian filter
                fseg = scipy.ndimage.gaussian_filter(u[i:i + j], sigma=sigma)
                f = np.concatenate((f, fseg))
                i += j
            return f, v
        else:
            return u, v

    # RANSAC implementation: https://github.com/ahojnnes/numpy-snippets/blob/master/ransac.py

    def _ransac(self, u, v):
        if len(u) > 1:
            data = np.vstack((v.ravel(), u.ravel())).T
            dr, thetar = self.ransac(data, LinearLeastSquares2D(), 2, 2)
            u = old_div((dr - v * math.sin(thetar)), math.cos(thetar))
        return u, v

    def compute_2d_points(self, image, roi_mask=True, refinement_method='SGF'):
        if image is not None:

            image = self.compute_line_segmentation(image, roi_mask=roi_mask)

            # Peak detection: center of mass
            s = image.sum(axis=1)
            v = np.where(s > 0)[0]
            u = old_div((self._weight_matrix * image).sum(axis=1)[v], s[v])

            if refinement_method == 'SGF':
                # Segmented gaussian filter
                u, v = self._sgf(u, v, s)
            elif refinement_method == 'RANSAC':
                # Random sample consensus
                u, v = self._ransac(u, v)
            return (u, v), image

    def get_texture_stream_frame(self, cam_image):
        return cam_image

    def get_calibration_stream_frame(self, cam_image):
        cam_image = self.drawCorners(cam_image)
        return cam_image

    def get_adjustment_stream_frame(self, cam_image):
        cv2.resize(cam_image, (self.config.camera.preview_resolution.width, self.config.camera.preview_resolution.height))
        cv2.line(cam_image, (int(0.5*cam_image.shape[1]),0), (int(0.5*cam_image.shape[1]), cam_image.shape[0]), (0,255,0), thickness=3, lineType=8, shift=0)
        return cam_image

    def drawCorners(self, image):
        corners = self.detect_corners(image)
        cv2.drawChessboardCorners(
            image, (self.config.calibration.pattern.columns, self.config.calibration.pattern.rows), corners, True)
        return image

    def get_laser_stream_frame(self, image, type='CAMERA'):

        if bool(self.settings.show_laser_overlay):
            points, ret_img = self.compute_2d_points(image, roi_mask=False)
            u, v = points
            c = list(zip(u, v))

            for t in c:
                cv2.line(image, (int(t[0]) - 1, int(t[1])), (int(t[0]) + 1, int(t[1])), (255, 0, 0), thickness=1,
                         lineType=8, shift=0)

        if bool(self.settings.show_calibration_pattern):
            cv2.line(image, (int(0.5*image.shape[1]), 0), (int(0.5*image.shape[1]), image.shape[0]), (0, 255, 0), thickness=1, lineType=8, shift=0)
            cv2.line(image, (0,int(0.5*image.shape[0])), (image.shape[1], int(0.5*image.shape[0])), (0, 255, 0), thickness=1, lineType=8, shift=0)


        return image

    #FIXME: rename color_image into texture_image
    def process_image(self, angle, laser_image, color_image=None):
        ''' Takes picture and angle (in degrees).  Adds to point cloud '''

        try:
            _theta = np.deg2rad(-angle)
            points_2d, image = self.compute_2d_points(laser_image)
            # FIXME; points_2d could contain empty arrays, resulting point_cloud to be None
            point_cloud = self.compute_point_cloud(_theta, points_2d, index=0)
            point_cloud = self.mask_point_cloud(point_cloud)

            if color_image is None:

                r, g, b = self.color

                color_image = np.zeros((self.image_height, self.image_width, 3), np.uint8)
                color_image[:, :, 0] = r
                color_image[:, :, 1] = g
                color_image[:, :, 2] = b

            u, v = points_2d

            texture = color_image[v, np.around(u).astype(int)].T

            return point_cloud, texture
        except Exception as e:
            self._logger.error("Process Error:"+str(e))
            return [], []

    def mask_image(self, image):
            mask = np.zeros(image.shape, np.uint8)
            mask[0:self.image_height, (old_div(self.image_width,2)):self.image_width] = image[0:self.image_height, (old_div(self.image_width,2)):self.image_width]
            return mask

    def mask_point_cloud(self, point_cloud):
        if point_cloud is not None and len(point_cloud) > 0:
            rho = np.sqrt(np.square(point_cloud[0, :]) + np.square(point_cloud[1, :]))
            z = point_cloud[2, :]
            turntable_radius = int(self.config.turntable.radius)
            additional_offset = 0.5
            idx = np.where((z > abs(self.config.calibration.platform_translation[0])+additional_offset) &
                           (rho >= -turntable_radius) &
                           (rho <= turntable_radius))[0]

            return point_cloud[:, idx]
        else:
            return point_cloud


    def compute_point_cloud(self, theta, points_2d, index):

        if points_2d[0].size == 0 or points_2d[1].size == 0:
             return None

        # Load calibration values
        R = np.matrix(self.config.calibration.platform_rotation)
        t = np.matrix(self.config.calibration.platform_translation).T
        # Compute platform transformation
        Xwo = self.compute_platform_point_cloud(points_2d, R, t, index)
        # Rotate to world coordinates
        c, s = np.cos(-theta), np.sin(-theta)
        Rz = np.matrix([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        Xw = Rz * Xwo
        # Return point cloud
        #if Xw.size > 0:
        #    return np.array(Xw)
        #else:
        #    return None

        return np.array(Xw)

    def compute_platform_point_cloud(self, points_2d, R, t, index):
        # Load calibration values
        n = self.config.calibration.laser_planes[index]['normal']
        d = self.config.calibration.laser_planes[index]['distance']
        # Camera system
        Xc = self.compute_camera_point_cloud(points_2d, d, n)
        # Compute platform transformation
        return R.T * Xc - R.T * t

    def compute_camera_point_cloud(self, points_2d, d, n):
        # Load calibration values

        fx = self.config.calibration.camera_matrix[0][0]
        fy = self.config.calibration.camera_matrix[1][1]
        cx = self.config.calibration.camera_matrix[0][2]
        cy = self.config.calibration.camera_matrix[1][2]

        ## if points_2d[0].size == 0 or points_2d[1].size == 0:
        ##     return np.array([]).reshape(3, 0)

        # Compute projection point
        u, v = points_2d
        x = np.concatenate((old_div((u - cx), fx), old_div((v - cy), fy), np.ones(len(u)))).reshape(3, len(u))


        ## points_for_undistort = np.array([np.concatenate((u, v)).reshape(2, len(u)).T])

        #print points_for_undistort.shape
        # use opencv's undistortPoints, which incorporates the distortion coefficients
        ## points_undistorted = cv2.undistortPoints(points_for_undistort, np.asanyarray(self.config.calibration.camera_matrix),
        ##                                         np.asanyarray(self.config.calibration.distortion_vector))

        ##u, v = np.hsplit(points_undistorted[0], points_undistorted[0].shape[1])

        ## make homogenous coordinates
        ## x = np.concatenate((u.T[0], v.T[0], np.ones(len(u)))).reshape(3, len(u))
        ## normalize to get unit direction vectors
        ## cam_point_direction = x / np.linalg.norm(x, axis=0)

        ### Compute laser intersection:
        ### dlc = dot(laser_normal, cam_point_direction) = projection of camera ray on laser-plane normal
        ### d / dlc = distance from cam center to 3D point
        ### cam_point_direction * d / dlc = 3D point

        #return d / np.dot(n, cam_point_direction) * cam_point_direction
        return old_div(d, np.dot(n, x) * x)

    def detect_corners(self, image, flags=None):
        corners = self._detect_chessboard(image, flags)
        return corners

    def detect_pose(self, image, flags=None):
        corners = self._detect_chessboard(image, flags)
        if corners is not None:
            ret, rvecs, tvecs = cv2.solvePnP(
                self.object_pattern_points, corners,
                self.config.calibration.camera_matrix, self.config.calibration.distortion_vector)
            if ret:
                return (cv2.Rodrigues(rvecs)[0], tvecs, corners)

    def detect_pattern_plane(self, pose):
        if pose is not None:
            R = pose[0]
            t = pose[1].T[0]
            c = pose[2]
            n = R.T[2]
            d = np.dot(n, t)
            return (d, n, c)


    def pattern_mask(self, image, corners):
        if image is not None:
            h, w, d = image.shape
            if corners is not None:
                corners = corners.astype(np.int)
                p1 = corners[0][0]
                p2 = corners[self.config.calibration.pattern.columns - 1][0]
                p3 = corners[self.config.calibration.pattern.columns * (self.config.calibration.pattern.rows - 1)][0]
                p4 = corners[self.config.calibration.pattern.columns * self.config.calibration.pattern.rows - 1][0]
                mask = np.zeros((h, w), np.uint8)
                points = np.array([p1, p2, p4, p3])
                cv2.fillConvexPoly(mask, points, 255)
                image = cv2.bitwise_and(image, image, mask=mask)
        return image

    def _detect_chessboard(self, image, flags=None):

        if image is not None:
            if self.config.calibration.pattern.rows > 2 and self.config.calibration.pattern.columns > 2:

                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

                if flags is None:
                    ret, corners = cv2.findChessboardCorners(gray, (self.config.calibration.pattern.columns, self.config.calibration.pattern.rows), None)
                else:
                    ret, corners = cv2.findChessboardCorners(gray, (self.config.calibration.pattern.columns, self.config.calibration.pattern.rows), flags=flags)

                if ret:
                    cv2.cornerSubPix(gray, corners, (11,11), (-1, -1), self._criteria)
                    return corners