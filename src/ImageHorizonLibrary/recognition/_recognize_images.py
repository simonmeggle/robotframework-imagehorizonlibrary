# -*- coding: utf-8 -*-
from os import listdir
from os.path import abspath, isdir, isfile, join as path_join
from time import time
from contextlib import contextmanager

import pyautogui as ag
from robot.api import logger as LOGGER
from .ImageDebugger import ImageDebugger

from skimage.feature import match_template, peak_local_max, canny
from skimage.color import rgb2gray
from skimage.io import imread

import numpy as np


from ..errors import ImageNotFoundException, InvalidImageException
from ..errors import ReferenceFolderException
        
class _RecognizeImages(object):

    def _normalize(self, path):
        if (not self.reference_folder or
                not isinstance(self.reference_folder, str) or
                not isdir(self.reference_folder)):
            raise ReferenceFolderException('Reference folder is invalid: '
                                           '"%s"' % self.reference_folder)
        if (not path or not isinstance(path, str)):
            raise InvalidImageException('"%s" is invalid image name.' % path)
        path = str(path.lower().replace(' ', '_'))
        path = abspath(path_join(self.reference_folder, path))
        if not path.endswith('.png') and not isdir(path):
            path += '.png'
        if not isfile(path) and not isdir(path):
            raise InvalidImageException('Image path not found: "%s".' % path)
        return path

    def click_image(self, reference_image):
        '''Finds the reference image on screen and clicks it once.

        ``reference_image`` is automatically normalized as described in the
        `Reference image names`.
        '''
        center_location = self.locate(reference_image)
        LOGGER.info('Clicking image "%s" in position %s' % (reference_image,
                                                            center_location))
        ag.click(center_location)
        return center_location

    def _click_to_the_direction_of(self, direction, location, offset,
                                   clicks, button, interval):
        raise NotImplementedError('This is defined in the main class.')

    def _locate_and_click_direction(self, direction, reference_image, offset,
                                    clicks, button, interval):
        location = self.locate(reference_image)
        self._click_to_the_direction_of(direction, location, offset, clicks,
                                        button, interval)

    def click_to_the_above_of_image(self, reference_image, offset, clicks=1,
                                    button='left', interval=0.0):
        '''Clicks above of reference image by given offset.

        See `Reference image names` for documentation for ``reference_image``.

        ``offset`` is the number of pixels from the center of the reference
        image.

        ``clicks`` and ``button`` are documented in `Click To The Above Of`.
        '''
        self._locate_and_click_direction('up', reference_image, offset,
                                         clicks, button, interval)

    def click_to_the_below_of_image(self, reference_image, offset, clicks=1,
                                    button='left', interval=0.0):
        '''Clicks below of reference image by given offset.

        See argument documentation in `Click To The Above Of Image`.
        '''
        self._locate_and_click_direction('down', reference_image, offset,
                                         clicks, button, interval)

    def click_to_the_left_of_image(self, reference_image, offset, clicks=1,
                                   button='left', interval=0.0):
        '''Clicks left of reference image by given offset.

        See argument documentation in `Click To The Above Of Image`.
        '''
        self._locate_and_click_direction('left', reference_image, offset,
                                         clicks, button, interval)

    def click_to_the_right_of_image(self, reference_image, offset, clicks=1,
                                    button='left', interval=0.0):
        '''Clicks right of reference image by given offset.

        See argument documentation in `Click To The Above Of Image`.
        '''
        self._locate_and_click_direction('right', reference_image, offset,
                                         clicks, button, interval)

    def copy_from_the_above_of(self, reference_image, offset):
        '''Clicks three times above of reference image by given offset and
        copies.

        See `Reference image names` for documentation for ``reference_image``.

        See `Click To The Above Of Image` for documentation for ``offset``.

        Copy is done by pressing ``Ctrl+C`` on Windows and Linux and ``⌘+C``
        on OS X.
        '''
        self._locate_and_click_direction('up', reference_image, offset,
                                         clicks=3, button='left', interval=0.0)
        return self.copy()

    def copy_from_the_below_of(self, reference_image, offset):
        '''Clicks three times below of reference image by given offset and
        copies.

        See argument documentation in `Copy From The Above Of`.
        '''
        self._locate_and_click_direction('down', reference_image, offset,
                                         clicks=3, button='left', interval=0.0)
        return self.copy()

    def copy_from_the_left_of(self, reference_image, offset):
        '''Clicks three times left of reference image by given offset and
        copies.

        See argument documentation in `Copy From The Above Of`.
        '''
        self._locate_and_click_direction('left', reference_image, offset,
                                         clicks=3, button='left', interval=0.0)
        return self.copy()

    def copy_from_the_right_of(self, reference_image, offset):
        '''Clicks three times right of reference image by given offset and
        copies.

        See argument documentation in `Copy From The Above Of`.
        '''
        self._locate_and_click_direction('right', reference_image, offset,
                                         clicks=3, button='left', interval=0.0)
        return self.copy()

    @contextmanager
    def _suppress_keyword_on_failure(self):
        keyword = self.keyword_on_failure
        self.keyword_on_failure = None
        yield None
        self.keyword_on_failure = keyword

    def _get_reference_images(self, reference_image):
        '''Return an absolute path for the given reference imge. 
        Return as a list of those if reference_image is a folder.
        '''
        is_dir = False
        try:
            if isdir(self._normalize(reference_image)):
                is_dir = True
        except InvalidImageException:
            pass
        is_file = False
        try:
            if isfile(self._normalize(reference_image)):
                is_file = True
        except InvalidImageException:
            pass
        reference_image = self._normalize(reference_image)

        reference_images = []
        if is_file:
            reference_images = [reference_image]
        elif is_dir:
            for f in listdir(self._normalize(reference_image)):
                if not isfile(self._normalize(path_join(reference_image, f))):
                    raise InvalidImageException(
                                            self._normalize(reference_image))
                reference_images.append(path_join(reference_image, f))
        return reference_images

    def _locate(self, reference_image, log_it=True):
        reference_images = self._get_reference_images(reference_image)

        location = None
        for ref_image in reference_images:
            location = self._try_locate(ref_image)
            if location != None:
                break

        if location is None:
            if log_it:
                LOGGER.info('Image "%s" was not found '
                            'on screen. (strategy: %s)' % (reference_image, self.strategy))
            self._run_on_failure()
            raise ImageNotFoundException(reference_image)
        if log_it:
            LOGGER.info('Image "%s" found at %r (strategy: %s)' % (reference_image, location, self.strategy))
        center_point = ag.center(location)
        x = center_point.x
        y = center_point.y
        if self.has_retina:
            x = x / 2
            y = y / 2
        return (x, y)

    def _locate_all(self, reference_image, haystack_image=None):   
        '''Tries to locate all occurrences of the reference image on the screen
        or on the haystack image, if given.
        Returns a list of location tuples (finds 0..n)''' 
        reference_images = self._get_reference_images(reference_image)   
        if len(reference_images) > 1: 
            raise InvalidImageException(
                f'Locating ALL occurences of MANY files ({", ".join(reference_images)}) is not supported.')        
        locations = self._try_locate(reference_images[0], locate_all=True, haystack_image=haystack_image)
        return locations

    def does_exist(self, reference_image):
        '''Returns ``True`` if reference image was found on screen or
        ``False`` otherwise. Never fails.

        See `Reference image names` for documentation for ``reference_image``.
        '''
        with self._suppress_keyword_on_failure():
            try:
                return bool(self._locate(reference_image, log_it=False))
            except ImageNotFoundException:
                return False

    def locate(self, reference_image):
        '''Locate image on screen.

        Fails if image is not found on screen.

        Returns Python tuple ``(x, y)`` of the coordinates.
        '''
        return self._locate(reference_image)

    def wait_for(self, reference_image, timeout=10):
        '''Tries to locate given image from the screen for given time.

        Fail if the image is not found on the screen after ``timeout`` has
        expired.

        See `Reference images` for further documentation.

        ``timeout`` is given in seconds.

        Returns Python tuple ``(x, y)`` of the coordinates.
        '''
        stop_time = time() + int(timeout)
        location = None
        with self._suppress_keyword_on_failure():
            while time() < stop_time:
                try:
                    location = self._locate(reference_image, log_it=False)
                    break
                except ImageNotFoundException:
                    pass
        if location is None:
            self._run_on_failure()
            raise ImageNotFoundException(self._normalize(reference_image))
        LOGGER.info('Image "%s" found at %r' % (reference_image, location))
        return location

    def debug_image(self):
        debug_app = ImageDebugger(self)
    
     
class _StrategyPyautogui():  

    def __init__(self, image_horizon_instance):
        self.ih_instance = image_horizon_instance

    def _try_locate(self, ref_image, haystack_image=None, locate_all=False):
        '''Tries to locate the reference image on the screen or the haystack_image. 
        Return values: 
        - locate_all=False: None or 1 location tuple (finds max 1)
        - locate_all=True:  None or list of location tuples (finds 0..n)
          (GUI Debugger mode)'''     

        ih = self.ih_instance   
        location = None
        if haystack_image is None:
            haystack_image = np.array(ag.screenshot())
        
        if locate_all: 
            locate_func = ag.locateAll    
        else:
            locate_func = ag.locate     #Copy below,take screenshots

        with ih._suppress_keyword_on_failure():
            try:
                if ih.has_cv and ih.confidence:                    
                    location_res = locate_func(ref_image,
                                                    haystack_image,
                                                    confidence=ih.confidence)
                else:
                    if ih.confidence:
                        LOGGER.warn("Can't set confidence because you don't "
                                    "have OpenCV (python-opencv) installed "
                                    "or a confidence level was not given.")
                    location_res = locate_func(ref_image, haystack_image)
            except ImageNotFoundException as ex:
                LOGGER.info(ex)
                pass
        if locate_all: 
            # convert the generator fo Box objects to a list of tuples
            location = [tuple(box) for box in location_res]
        else: 
            # Single Box
            location = location_res
        return location



class _StrategySkimage():
    _SKIMAGE_DEFAULT_CONFIDENCE = 0.99

    def __init__(self, image_horizon_instance):
        self.ih_instance = image_horizon_instance

    def _try_locate(self, ref_image, haystack_image=None, locate_all=False):
        '''Tries to locate the reference image on the screen or the provided haystack_image. 
        Return values: 
        - locate_all=False: None or 1 location tuple (finds max 1)
        - locate_all=True:  None or list of location tuples (finds 0..n)
          (GUI Debugger mode)'''

        ih = self.ih_instance
        confidence = ih.confidence or self._SKIMAGE_DEFAULT_CONFIDENCE        
        with ih._suppress_keyword_on_failure():            
            needle_img = imread(ref_image, as_gray=True)
            haystack_img_height, needle_img_width = needle_img.shape   
            if haystack_image is None:
                haystack_img_gray = rgb2gray(np.array(ag.screenshot()))
            else:
                haystack_img_gray = rgb2gray(haystack_image)
            # detect edges on both images
            ih.needle_edge = self.detect_edges(needle_img)
            ih.haystack_edge = self.detect_edges(haystack_img_gray)  
            # find match peaks          
            ih.peakmap = match_template(ih.haystack_edge, ih.needle_edge)

            if locate_all: 
                # https://stackoverflow.com/questions/48732991/search-for-all-templates-using-scikit-image                
                peaks = peak_local_max(ih.peakmap,threshold_rel=confidence) 
                peak_coords = zip(peaks[:,1], peaks[:,0])
                locations = []
                for i, pk in enumerate(peak_coords):
                    loc = (pk[0], pk[1], needle_img_width, haystack_img_height)
                    #yield loc
                    locations.append(loc)
                if len(locations) > 0: 
                    location = locations
                else: 
                    location = []
            else: 
                ij = np.unravel_index(np.argmax(ih.peakmap), ih.peakmap.shape)
                x, y = ij[::-1]
                peak = ih.peakmap[y][x]
                if peak > confidence:                      
                    locations = [(x, y, needle_img_width, haystack_img_height)]                
                                    
                # Transform index to coordinates of highest peak
                ij = np.unravel_index(np.argmax(ih.peakmap), ih.peakmap.shape)
                # Extract coordinates of the highest peak
                x, y = ij[::-1]
                # higest peak level
                peak = ih.peakmap[y][x]        
                if peak > confidence:      
                    needle_img_height, needle_img_width = needle_img.shape          
                    location = (x, y, needle_img_width, needle_img_height)
                else:
                    location = None
            return location

    def _detect_edges(self, img, sigma, low, high):
        edge_img = canny(
            image=img,
            sigma=sigma,
            low_threshold=low,
            high_threshold=high,
        )
        return edge_img

    def detect_edges(self, img):
        '''Apply edge detection on a given image'''
        return self._detect_edges(
            img,
            self.ih_instance.edge_sigma,
            self.ih_instance.edge_low_threshold,
            self.ih_instance.edge_low_threshold
            )

