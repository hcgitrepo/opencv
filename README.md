# Monitoring with a cam in realtime and replaying stored videos with OpenCV on a web browser

This is a web implementation in order to monitor with a cam and replay recorded videos. It is built with Flask and socketio.

You can do:
- monitor a video from your cam (need some modification on source code)
- play videos stored in your Flask server with some useful functions: play, pause, fast forward, and rewind

You can't do:
- record a video from a cam (currently not available so you need to implement this function by yourself with VideoWriter class)
