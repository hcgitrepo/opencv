# import numpy as np
import imutils
import time
import cv2
# from flask import Response
from flask import Flask
from flask import render_template
import threading
import datetime
from flask_socketio import SocketIO
import base64
import os

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

@app.route("/")
def index():
    res = os.listdir('./')
    res = [x for x in res if x.split('.')[-1] == 'mp4']
    return render_template('index.html', file_list=res)

@app.route("/load/<file_name>", methods=['GET', 'POST'])
def load(file_name):
    global file_video
    file_video = VideoControl(filename=file_name, namespace='file_test')
    file_video.load()
    return 'video loaded'

@app.route("/play", methods=['GET', 'POST'])
def play():
    file_video.play()
    return 'video started'

@app.route("/pause", methods=['GET', 'POST'])
def pause():
    file_video.pause()
    return 'video paused'

@app.route("/ff", methods=['GET', 'POST'])
def ff():
    file_video.ff()
    return 'video 5s ff'

@app.route("/rew", methods=['GET', 'POST'])
def rewind():
    file_video.rew()
    return 'video 5s rew'

@app.route("/seek/<frame_pos>", methods=['GET', 'POST'])
def seek(frame_pos):
    file_video.seek(frame_pos)
    return 'video seek'

class VideoControl():
    def __init__(self, filename=None, is_realtime=False, image_width=600, namespace=''):
        self.filename = filename
        self.vc = None
        self.fps = None
        self.frame = None
        self.frame_info = None
        self.pause_frame_pos = 0
        self.read_status = 0
        self.feed_status = 0
        self.image_width = image_width
        self.namespace = namespace
        self.read_thread = None
        self.feed_thread = None
        self.curr_frame_pos = None
        self.total_frame_pos = None
        self.is_realtime = is_realtime
        self.lock = threading.Lock()
        if not is_realtime and filename is None:
            raise Exception('filename not found')

    def read_frame(self):
        print(f'read frame started: {self.namespace}')

        start_time = time.time()
        while self.read_status:
            frame_info = {}

            flag, frame = self.vc.read()

            if frame is None or flag is False:
                break

            frame = imutils.resize(frame, width=self.image_width)
            
            # ML models can be used to detect and classify objects here 

            # display information on each frame
            cur_timestamp = datetime.datetime.now()
            cv2.putText(frame, cur_timestamp.strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
            
            # information for replay
            if not self.is_realtime:
                frame_info['time'] = cur_timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
                curr_frame_pos = self.vc.get(cv2.CAP_PROP_POS_FRAMES)
                total_frame_pos = self.vc.get(cv2.CAP_PROP_FRAME_COUNT)
                frame_info['curr_frame_pos'] = curr_frame_pos
                frame_info['total_frame_pos'] = total_frame_pos
                frame_info['curr_sec'] = int(curr_frame_pos / self.fps)
                frame_info['total_sec'] = int(total_frame_pos / self.fps)
                ss = frame_info["curr_sec"] % 60
                mm = int(frame_info["curr_sec"] / 60) % 60
                hh = int(frame_info["curr_sec"] / 60 / 60)
                frame_info['curr_hhmmss'] = f'{hh}:{mm:02d}:{ss:02d}'
                ss = frame_info["total_sec"] % 60
                mm = int(frame_info["total_sec"] / 60) % 60
                hh = int(frame_info["total_sec"] / 60 / 60)
                frame_info['total_hhmmss'] = f'{hh}:{mm:02d}:{ss:02d}'
                print(f'POS: {curr_frame_pos}/{total_frame_pos} (expected {self.fps:.2f}) Elapsed: {(time.time()-start_time)}\r', end='')

            # with self.lock:
            self.frame = frame.copy()
            self.frame_info = frame_info.copy()

            elapsed = time.time()-start_time
            next_pos = int(elapsed * self.fps) + self.pause_frame_pos
            self.vc.set(cv2.CAP_PROP_POS_FRAMES, next_pos)

            # reduce processing speed
            socketio.sleep(0.1)

        print(f'read frame stopped: {self.namespace}')

    def feed_frame(self):
        print(f'feed frame started: {self.namespace}')

        while self.feed_status:
            # with self.lock:
            if self.frame is None:
                continue

            flag, img = cv2.imencode('.jpg', self.frame)
            byte_img = base64.encodebytes(img.tobytes()).decode('utf-8')

            if not flag:
                continue
            
            socketio.emit(f'feed_frame_{self.namespace}', byte_img)
            socketio.emit(f'feed_frame_info_{self.namespace}', self.frame_info)

            socketio.sleep(0.1)

        print(f'feed frame stopped: {self.namespace}')

    def load(self):
        if self.read_thread is not None or self.feed_thread is not None:
            self.pause_frame_pos = 0
            self.read_status = 0
            self.feed_status = 0
            self.read_thread.join()
            self.feed_thread.join()

        # with self.lock:
        self.vc = cv2.VideoCapture(self.filename) 
        self.fps = self.vc.get(cv2.CAP_PROP_FPS)

        self.curr_frame_pos = self.vc.get(cv2.CAP_PROP_POS_FRAMES)
        self.total_frame_pos = self.vc.get(cv2.CAP_PROP_FRAME_COUNT)

        print(f'video loaded: {self.namespace}')

    def play(self):
        # with self.lock:
        self.read_thread = threading.Thread(target=self.read_frame)
        self.read_thread.daemon = True
        self.read_status = 1
        self.read_thread.start()

        self.feed_thread = threading.Thread(target=self.feed_frame)
        self.feed_thread.daemon = True
        self.feed_status = 1
        self.feed_thread.start()
        print(f'video started: {self.namespace}')

    def pause(self):
        # with self.lock:
        self.read_status = 0
        self.feed_status = 0
        self.read_thread.join()
        self.feed_thread.join()
        self.pause_frame_pos = self.vc.get(cv2.CAP_PROP_POS_FRAMES)
        print(f'video paused: {self.namespace}')

    def ff(self):
        self.pause()
        # with self.lock:
        self.pause_frame_pos += int(self.fps*5)
        self.vc.set(cv2.CAP_PROP_POS_FRAMES, self.pause_frame_pos)
        self.play()
        print(f'video 5s ff: {self.namespace}')

    def rew(self):
        self.pause()
        # with self.lock:
        self.pause_frame_pos -= int(self.fps*5)
        self.vc.set(cv2.CAP_PROP_POS_FRAMES, self.pause_frame_pos)
        self.play()
        print(f'video 5s rew: {self.namespace}')

    def seek(self, frame_pos):
        self.pause()
        # socketio.sleep(0.2)
        # with self.lock:
        self.pause_frame_pos = int(frame_pos)
        self.vc.set(cv2.CAP_PROP_POS_FRAMES, self.pause_frame_pos)
        self.play()
        print(f'video seek: {self.namespace}')


realtime_video = VideoControl(filename='realtime_sample.mp4', namespace='realtime_test', is_realtime=True)
realtime_video.load()
realtime_video.play()
file_video = None


if __name__ == '__main__':
    # app.run(host='0.0.0.0', port='8000', debug=True, threaded=True, use_reloader=False)
    socketio.run(app, host='0.0.0.0', debug=True, use_reloader=False)
	# eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)
