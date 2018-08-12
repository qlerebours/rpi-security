# -*- coding: utf-8 -*-

import logging
import time

from imutils.video import VideoStream
import datetime
import imutils
import cv2

logger = logging.getLogger()


def monitor_alarm_state(rpis, camera):
	"""
	This function monitors and updates the alarm state, starts/stops motion detection when
	state is armed and takes photos when motion detection is triggered.
	"""
	logger.info("thread running")
	while True:
		time.sleep(0.1)
		rpis.state.check()
		if rpis.state.current == 'armed':
			vs = VideoStream(usePiCamera=True).start()
			time.sleep(2.0)
			first_frame = None
			video_in_progress = True
			logger.debug("Started motion detection with VideoStream from RpiCamera")
			# loop over the frames of the video
			while video_in_progress:
				# grab the current frame
				frame = vs.read()
				frame = frame if args.get("video", None) is None else frame[1]

				# if frame is initialized, we have not reach the end of the video
				if frame is not None:
					result = handle_new_frame(frame, first_frame, args)
					if result is not None:
						first_frame = result
				else:
					video_in_progress = False

			# cleanup the camera and close any open windows
			vs.stop() if args.get("video", None) is None else vs.release()
			cv2.destroyAllWindows()





			# while not camera.lock.locked():
			#     logger.info("In while: Camera is not locked")
			#     camera.start_motion_detection()
			#     rpis.state.check()
			#     if rpis.state.current is not 'armed':
			#         break
			#     if camera.motion_detector.camera_trigger.is_set():
			#         camera.stop_motion_detection()
			#         camera.trigger_camera()
			#         camera.motion_detector.camera_trigger.clear()
			# else:
			#     camera.stop_motion_detection()
		else:
			camera.stop_motion_detection()

def handle_new_frame(frame, first_frame, args):
	logger.debug("New frame")
	motion_detected = False
	print_image("images/test", frame)
	# resize the frame, convert it to grayscale, and blur it
	# frame = imutils.resize(frame, width=500)
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

	# loop over the contours
	for c in cnts:
		# if the contour is too small, ignore it
		if cv2.contourArea(c) < args["min_area"]:
			continue

		# compute the bounding box for the contour, draw it on the frame,
		# and update the text
		(x, y, w, h) = cv2.boundingRect(c)
		cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
		motion_detected = True
		print_image("images/frame", frame)
		print_image("images/gray", gray)
		print_image("images/abs_diff", frame_detla)
		print_image("images/tresh", thresh)

	return None



def print_image(name, image):
	cv2.imwrite(name + '_' + datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ".jpg", image)
