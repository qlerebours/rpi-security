# -*- coding: utf-8 -*-

import logging
import os
import time
from picamera.array import PiMotionAnalysis
from picamera import PiCamera
import numpy as np
from PIL import Image
from threading import Lock, Event
from queue import Queue
from .exit_clean import exit_error
from datetime import datetime
import json

# from imutils.video import VideoStream
import datetime
import imutils
import time
import cv2

logger = logging.getLogger()


class RpisCamera(object):
    '''
    A wrapper for the camera. Runs motion detection, provides a queue for photos,
    captues photos and GIFs.
    '''
    def __init__(self, photo_size, gif_size, motion_size, camera_vflip,
            camera_hflip, motion_detection_setting, camera_capture_length,
            camera_mode):
        self.photo_size = photo_size
        self.gif_size = gif_size
        self.camera_vflip = camera_vflip
        self.camera_hflip = camera_hflip
        self.lock = Lock()
        self.queue = Queue()
        self.motion_magnitude = motion_detection_setting[0]
        self.motion_vectors = motion_detection_setting[1]
        self.motion_framerate = 5
        self.motion_size = motion_size
        self.temp_directory = '/var/tmp'
        self.camera_save_path = '/var/tmp'
        self.camera_capture_length = camera_capture_length
        self.camera_mode = camera_mode

        try:
            self.camera = PiCamera()
            self.camera.vflip = self.camera_vflip
            self.camera.hflip = self.camera_hflip
            self.camera.led = False
        except Exception as e:
            exit_error('Camera module failed to intialise with error {0}'.format(repr(e)))

        # self.motion_detector = self.MotionDetector(self.camera)
        # self.motion_detector.motion_magnitude = self.motion_magnitude
        # self.motion_detector.motion_vectors = self.motion_vectors

    # class MotionDetector(PiMotionAnalysis):
    #     camera_trigger = Event()
    #     motion_magnitude = 60
    #     motion_vectors = 10
    #     motion_settle_time = 1
    #     motion_detection_started = 0
    #     is_first = True
	#
    #     def motion_detected(self, vector_count):
    #         if time.time() - self.motion_detection_started < self.motion_settle_time:
    #             logger.debug('Ignoring initial motion due to settle time')
    #             return
    #         logger.info("Type of vector_count variable is: %s", type(vector_count).__name__)
    #         logger.info("Type of motion_vectors variable is: %s", type(self.motion_vectors).__name__)
    #         logger.info('Motion detected. Vector count: %s. Threshold: %s', json.dumps(vector_count.item()), json.dumps(self.motion_vectors))
    #         self.camera_trigger.set()
	#
    #     def analyse(self, a):
    #         magnitude = np.sqrt(
    #             np.square(a['x'].astype(np.float)) +
    #             np.square(a['y'].astype(np.float))
    #         ).clip(0, 255).astype(np.uint8)
    #         vector_count = (magnitude > self.motion_magnitude).sum()
    #         if vector_count > self.motion_vectors:
    #             logger.info("Type of 'a' variable is: %s", type(a).__name__)
    #             logger.info("Motion detected with magnitude: %s", json.dumps(magnitude.tolist()))
    #             self.motion_detected(vector_count)

    def take_photo(self, filename_extra_suffix=''):
        """
        Captures a photo and saves it disk.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        photo = '{0}/rpi-security-{1}{2}.jpeg'.format(self.camera_save_path, timestamp, filename_extra_suffix)
        try:
            self.set_normal_settings()
            with self.lock:
                while self.camera.recording:
                    time.sleep(0.1)
                time.sleep(2)
                self.camera.resolution = self.photo_size
                self.camera.capture(photo, use_video_port=False)
        except Exception as e:
            logger.error('Failed to take photo: {0}'.format(repr(e)))
            return None
        else:
            logger.info("Captured image: {0}".format(photo))
            return photo

    def take_gif(self):
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        gif = '{0}/rpi-security-{1}.gif'.format(self.camera_save_path, timestamp)
        temp_jpeg_path = '{0}/rpi-security-{1}-gif-part'.format(self.temp_directory, timestamp)
        jpeg_files = ['{0}-{1}.jpg'.format(temp_jpeg_path, i) for i in range(self.camera_capture_length*3)]
        try:
            self.set_normal_settings()
            for jpeg in jpeg_files:
                with self.lock:
                    while self.camera.recording:
                        time.sleep(0.1)
                    self.camera.resolution = self.gif_size
                    self.camera.capture(jpeg)
            im=Image.open(jpeg_files[0])
            jpeg_files_no_first_frame=[x for x in jpeg_files if x != jpeg_files[0]]
            ims = [Image.open(i) for i in jpeg_files_no_first_frame]
            im.save(gif, append_images=ims, save_all=True, loop=0, duration=200)
            for jpeg in jpeg_files:
                os.remove(jpeg)
        except Exception as e:
            logger.error('Failed to create GIF: {0}'.format(repr(e)))
            return None
        else:
            logger.info("Captured gif: {0}".format(gif))
            return gif

    def trigger_camera(self):
        if self.camera_mode == 'gif':
            captured = self.take_gif()
            self.queue.put(captured)
        elif self.camera_mode == 'photo':
            for i in range(0, self.camera_capture_length, 1):
                captured = self.take_photo(filename_extra_suffix='-{0}'.format(i))
                self.queue.put(captured)
        else:
            logger.error('Unsupported camera_mode: {0}'.format(self.camera_mode))

    def set_normal_settings(self):
        self.camera.awb_mode = 'auto'
        self.camera.exposure_mode = 'auto'

    def set_motion_settings(self):
        self.camera.resolution = self.motion_size
        self.camera.framerate = self.motion_framerate
        exposure_speed = self.camera.exposure_speed
        awb_gains = self.camera.awb_gains
        self.camera.shutter_speed = exposure_speed
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = awb_gains
        self.camera.exposure_mode = 'off'

    def start_motion_detection(self):
        logger.debug("Will initialize RpiCamera stream")
        # vs = VideoStream(usePiCamera=True).start()
        min_area = 500
        past_frame = None
        video_in_progress = True
        logger.debug("Started motion detection with VideoStream from RpiCamera")
        # loop over the frames of the video
        while video_in_progress:
            picture_path = '/tmp/rpi-security-current.jpg'
            self.camera.capture(picture_path, use_video_port=False)
            time.sleep(0.5)
            # grab the current frame
            frame = cv2.imread(picture_path)

            # if frame is initialized, we have not reach the end of the video
            if frame is not None:
                new_frame = self.handle_new_frame(frame, past_frame, min_area)
                if new_frame is not None:
                    past_frame = new_frame
            else:
                video_in_progress = False

    def handle_new_frame(self, frame, first_frame, min_area):
        logger.debug("New frame, with typeof frame=" + type(frame).__name__ + " and type of first_frame" + type(first_frame).__name__)
        (h, w) = frame.shape[:2]
        r = 500 / float(w)
        dim = (500, int(h * r))
        frame = cv2.resize(frame, dim, cv2.INTER_AREA)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # if the first frame is None, initialize it
        if first_frame is None:
            first_frame = gray
            return first_frame

        # compute the absolute difference between the current frame and first frame
        frame_detla = cv2.absdiff(first_frame, gray)
        # then apply a threshold to remove camera motion and other false positives (like light changes)
        thresh = cv2.threshold(frame_detla, 25, 255, cv2.THRESH_BINARY)[1]

        # dilate the thresholded image to fill in holes, then find contours on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if imutils.is_cv2() else cnts[1]

        self.print_image("frame", frame)
        self.print_image("gray", gray)
        self.print_image("abs_diff", frame_detla)
        self.print_image("thresh", thresh)

        # loop over the contours
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < min_area:
                continue

            # compute the bounding box for the contour, draw it on the frame,
            # and update the text
            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            self.handle_motion_detected(frame, gray, frame_detla, thresh)
        else:
            logger.debug("Didn't find motion")

        return None

    def handle_motion_detected(self, frame, gray, frame_detla, thresh):
        self.trigger_camera()
        self.print_image("frame", frame)
        self.print_image("gray", gray)
        self.print_image("abs_diff", frame_detla)
        self.print_image("tresh", thresh)
        return

    def print_image(self, name, image):
        cv2.imwrite('/tmp/' + name + '_' + datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ".jpg", image)

    def stop_motion_detection(self):
        try:
            if not self.camera.recording:
                return
            else:
                logger.debug("Stopping motion detection")
                self.camera.stop_recording()
        except Exception as e:
            logger.error('Error in stop_motion_detection: {0}'.format(repr(e)))

    def clear_queue(self):
        with self.queue.mutex:
            self.queue.queue.clear()
