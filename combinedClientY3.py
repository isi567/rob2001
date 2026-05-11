# import standard packages
import time
import numpy as np
import socket
import sys
# import trilobot package 
from trilobot import Trilobot
from picamera2 import Picamera2
# import vision package
import cv2
# import additional code -- this is where the real vision code lives.
import find

# network protocol constants
MSG_REGISTER = 'REGISTER'
MSG_COLOUR = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'
MSG_LIST = 'LIST'
MSG_ERROR = 'ERROR'

HOST = '10.247.26.138'
PORT = 50007

# define client thread state variables
STATE_CLIENT_RUNNING       = 2
STATE_CLIENT_EXITING       = 1
STATE_CLIENT_SEND_COLOUR   = 4
STATE_CLIENT_RECEIVE_COLOUR = 5

# Mission state variables
STATE_MISSION_LOOKING_FOR_GREEN = 10
STATE_MISSION_FOUND_GREEN = 11
STATE_MISSION_LOOKING_FOR_RED = 12
STATE_MISSION_RETURN_TO_RED = 13
STATE_MISSION_WAITING = 14

# Movement parameters
DRIVE_SPEED = 1.0
DRIVE_TIME  = 1.2
TURN_SPEED  = 0.6
TURN_TIME   = 0.6

colour_ranges = {
    'red': {'lower': np.array([0, 120, 120]), 'upper': np.array([10, 255, 255]), 'draw_colour': (0, 0, 255)},
    'green': {'lower': np.array([50, 80, 80]), 'upper': np.array([70, 255, 255]), 'draw_colour': (0, 255, 0)}
}

def go_forward():
    tbot.forward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def go_backward():
    tbot.backward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def turn_left():
    tbot.curve_forward_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def turn_right():
    tbot.curve_forward_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_right():
    tbot.turn_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def red_lights():
    tbot.fill_underlighting((255, 0, 0))

def green_lights():
    tbot.fill_underlighting((0, 255, 0))

def lights_off():
    tbot.clear_underlighting()

def apply_colour_lights(colour):
    if colour == 'red': red_lights()
    elif colour == 'green': green_lights()

def get_distance():
    return tbot.read_distance()

def safe_cleanup(sock=None, camera=None):
    try: tbot.stop()
    except: pass
    try: lights_off()
    except: pass
    if camera: camera.stop()
    if sock: sock.close()

if len(sys.argv) < 3:
    print('usage: python script.py <ID> <TARGET_ID>')
    sys.exit(1)

client_id = sys.argv[1].lower()
target_client = sys.argv[2]
tbot = Trilobot()
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()

cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    cs.connect((HOST, PORT))
    cs.settimeout(0.5)
    cs.sendall((MSG_REGISTER + ' ' + client_id + '\n').encode())
    
    state = STATE_CLIENT_RUNNING
    mission_state = STATE_MISSION_WAITING
    waiter_has_food_order = False 
    last_sent_colour = None
    last_send_time = 0.0
    min_send_interval = 0.8
    recv_buffer = ''
    red_found_time = 0.0

    while True:
        now = time.time()
        img = picam2.capture_array()
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        centers = find.find_color_centers(img_bgr, colour_ranges)
        detected_colour = None

        # Visual feedback for detection
        if centers.get("red"):
            red_lights()
            detected_colour = 'red'
        elif centers.get("green"):
            green_lights()
            detected_colour = 'green'
        else:
            lights_off()

        # MISSION LOGIC
        if mission_state == STATE_MISSION_LOOKING_FOR_GREEN:
            if centers.get("green"):
                green_x = centers.get("green")[0]
                if green_x < 280: turn_left()
                elif green_x > 360: turn_right()
                else:
                    if get_distance() < 15:
                        tbot.stop()
                        mission_state = STATE_MISSION_FOUND_GREEN
                    else: go_forward()
            else: sharp_right()

        elif mission_state == STATE_MISSION_FOUND_GREEN:
            if client_id == "waiter":
                msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': found'
                cs.sendall((msg + '\n').encode())
            mission_state = STATE_MISSION_LOOKING_FOR_RED

        elif mission_state == STATE_MISSION_LOOKING_FOR_RED:
            if centers.get("red"):
                red_x = centers.get("red")[0]
                if red_x < 280: turn_left()
                elif red_x > 360: turn_right()
                else:
                    if get_distance() < 10: mission_state = STATE_MISSION_RETURN_TO_RED
                    else: go_forward()
            else: sharp_right()

        elif mission_state == STATE_MISSION_RETURN_TO_RED:
            tbot.stop()
            if red_found_time == 0.0: red_found_time = now
            if now - red_found_time >= 3.0:
                mission_state = STATE_MISSION_WAITING
                waiter_has_food_order = False
                red_found_time = 0.0

        # NETWORK LOGIC
        if state == STATE_CLIENT_RUNNING:
            state = STATE_CLIENT_RECEIVE_COLOUR

        elif state == STATE_CLIENT_RECEIVE_COLOUR:
            try:
                chunk = cs.recv(1024)
                if not chunk: break
                recv_buffer += chunk.decode()
                lines = recv_buffer.split('\n')
                recv_buffer = lines[-1]
                for line in lines[:-1]:
                    msg = line.strip()
                    if ' : ' in msg: # simplified parse for instructions
                        payload = msg.split(' : ')[-1].lower()
                        
                        if client_id == "waiter":
                            if payload == "food":
                                waiter_has_food_order = True
                            elif payload == "green" and waiter_has_food_order:
                                mission_state = STATE_MISSION_LOOKING_FOR_GREEN
                        
                        elif client_id == "chef":
                            if payload == "food":
                                out = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': green'
                                cs.sendall((out + '\n').encode())
            except socket.timeout: pass
            state = STATE_CLIENT_RUNNING

except KeyboardInterrupt: pass
finally: safe_cleanup(cs, picam2)