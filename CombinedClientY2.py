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

# network protocol constants (must match roboserver1.py)
MSG_REGISTER = 'REGISTER'
MSG_COLOUR = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'
MSG_LIST = 'LIST'
MSG_ERROR = 'ERROR'

HOST = '10.247.72.18'
PORT = 50007

# define client thread state variables
STATE_CLIENT_STARTING      = 0
STATE_CLIENT_EXITING       = 1
STATE_CLIENT_RUNNING       = 2
STATE_CLIENT_ERROR         = 3
STATE_CLIENT_SEND_COLOUR   = 4
STATE_CLIENT_RECEIVE_COLOUR = 5

# Mission state variables
STATE_MISSION_LOOKING_FOR_GREEN = 10
STATE_MISSION_FOUND_GREEN = 11
STATE_MISSION_LOOKING_FOR_RED = 12
STATE_MISSION_RETURN_TO_RED = 13
STATE_MISSION_WAITING = 14

# set parameters for controlling how far the trilobot moves
DRIVE_SPEED = 1.0
DRIVE_TIME  = 1.2
TURN_SPEED  = 0.6
TURN_TIME   = 0.6

# Set colour thresholds. The thresholds are in the HSV colour space
colour_ranges = {
        'red': {
            'lower': np.array([0, 120, 120]),
            'upper': np.array([10, 255, 255]),
            'draw_colour': (0, 0, 255)  # BGR format
        },
        'green': {
            'lower': np.array([50, 80, 80]),
            'upper': np.array([70, 255, 255]),
            'draw_colour': (0, 255, 0)
        }
    }

# define motion functions
def go_forward():
    print( 'moving forward' )
    tbot.forward( DRIVE_SPEED )
    time.sleep( DRIVE_TIME )
    tbot.stop()

def go_backward():
    print( 'moving backward' )
    tbot.backward( DRIVE_SPEED )
    time.sleep( DRIVE_TIME )
    tbot.stop()

def turn_left():
    print( 'turning left' )
    tbot.curve_forward_left( TURN_SPEED )
    time.sleep( TURN_TIME )
    tbot.stop()

def turn_right():
    print( 'turning right' )
    tbot.curve_forward_right( TURN_SPEED )
    time.sleep( TURN_TIME )
    tbot.stop()

def sharp_right():
    print( 'sharp right' )
    tbot.turn_right( TURN_SPEED )
    time.sleep( TURN_TIME )
    tbot.stop()

def sharp_left():
    print( 'sharp left' )
    tbot.turn_left( TURN_SPEED )
    time.sleep( TURN_TIME )
    tbot.stop()

# define functions that turn on underlights
def red_lights():
    print( 'red lights' )
    tbot.fill_underlighting(( 255, 0, 0 ))

def green_lights():
    print( 'green lights' )
    tbot.fill_underlighting(( 0, 255, 0 ))

def blue_lights():
    print( 'blue lights' )
    tbot.fill_underlighting(( 0, 0, 255 ))

def yellow_lights():
    print( 'yellow lights' )
    tbot.fill_underlighting(( 255, 255, 0 ))

def lights_off():
    print( 'lights out!' )
    tbot.clear_underlighting()

def apply_colour_lights( colour ):
    if ( colour == 'red' ):
        red_lights()
    elif ( colour == 'green' ):
        green_lights()
    elif ( colour == 'blue' ):
        blue_lights()
    elif ( colour == 'yellow' ):
        yellow_lights()

# define distance sensor function
def get_distance():
    distance = tbot.read_distance()
    print( 'distance from nearest object = %fcm' % ( distance ))
    return( distance )

def safe_cleanup( sock=None, camera=None ):
    try:
        tbot.stop()
    except Exception:
        pass
    try:
        lights_off()
    except Exception:
        pass
    try:
        if ( camera is not None ):
            camera.stop()
    except Exception:
        pass
    try:
        if ( sock is not None ):
            sock.close()
    except Exception:
        pass
    try:
        gpio_module = __import__( 'RPi.GPIO', fromlist=[ 'GPIO' ] )
        gpio_module.cleanup()
    except Exception:
        pass

#-----
# main
#-----

if ( len( sys.argv ) < 3 ):
    print( 'usage: python trilo_vision_mimi_2.py <ID> <TARGET_ID>' )
    sys.exit( 1 )

client_id = sys.argv[1]
target_client = sys.argv[2]
server_host = HOST
server_port = PORT

print( 'hello!' )
tbot = Trilobot()

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()

cs = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
try:
    cs.connect(( server_host, server_port ))
    cs.settimeout( 0.5 )
    register_msg = MSG_REGISTER + ' ' + client_id
    cs.sendall( ( register_msg + '\n' ).encode() )
    try:
        register_reply = cs.recv( 1024 ).decode().strip()
        if ( register_reply ):
            print( '[vision %s] register reply: %s' % ( client_id, register_reply ))
    except socket.timeout:
        print( '[vision %s] register reply timeout (continuing)' % ( client_id ))

    state = STATE_CLIENT_RUNNING
    mission_state = STATE_MISSION_LOOKING_FOR_GREEN
    last_sent_colour = None
    last_send_time = 0.0
    min_send_interval = 0.8
    recv_buffer = ''
    has_received_confirmation = False
    green_found_time = 0.0
    red_found_time = 0.0
    green_detection_threshold = 1.0

    while True:
        img = picam2.capture_array()
        try:
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception:
            img_bgr = img

        centers = find.find_color_centers(img_bgr, colour_ranges)
        detected_colour = None

        # --- SEPARATE COLOUR DETECTION BLOCKS ---
        if centers.get("red") is not None:
            print("Red object at x:", centers.get("red")[0], "y: ", centers.get("red")[1])
            red_lights()
            detected_colour = 'red'
        else:
            print("No red objects found")
            lights_off()

        if centers.get("green") is not None:
            print("Green object at x:", centers.get("green")[0], "y: ", centers.get("green")[1])
            green_lights()
            detected_colour = 'green'
        else:
            print("No green objects found")
            lights_off()
        # ----------------------------------------

        # MISSION LOGIC
        if mission_state == STATE_MISSION_LOOKING_FOR_GREEN:
            if centers.get("green") is not None:
                green_x = centers.get("green")[0]
                distance = get_distance()
                if green_x < 280:
                    turn_left()
                elif green_x > 360:
                    turn_right()
                else:
                    if distance < 15:
                        print('[vision %s] Reached green, moving to FOUND_GREEN' % (client_id))
                        tbot.stop()
                        mission_state = STATE_MISSION_FOUND_GREEN
                    else:
                        go_forward()
            else:
                sharp_right()

        elif mission_state == STATE_MISSION_FOUND_GREEN:
            if target_client:
                out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': green_found'
                try:
                    cs.sendall( (out_msg + '\n').encode() )
                except Exception as e:
                    print( '[vision %s] send error: %s' % ( client_id, e ))
            mission_state = STATE_MISSION_LOOKING_FOR_RED

        elif mission_state == STATE_MISSION_LOOKING_FOR_RED:
            if centers.get("red") is not None:
                red_x = centers.get("red")[0]
                now = time.time()
                if red_found_time == 0.0:
                    red_found_time = now
                if now - red_found_time >= green_detection_threshold:
                    mission_state = STATE_MISSION_RETURN_TO_RED
                    red_found_time = 0.0
                else:
                    if red_x < 280:
                        turn_left()
                    elif red_x > 360:
                        turn_right()
                    else:
                        if get_distance() < 10:
                            go_backward()
                        else:
                            go_forward()
            else:
                red_found_time = 0.0
                sharp_right()

        elif mission_state == STATE_MISSION_RETURN_TO_RED:
            if centers.get("red") is not None:
                red_x = centers.get("red")[0]
                if red_x < 280: turn_left()
                elif red_x > 360: turn_right()
                else:
                    if get_distance() < 10: go_backward()
                    else: go_forward()
            else:
                sharp_right()
            
            now = time.time()
            if red_found_time == 0.0: red_found_time = now
            if now - red_found_time >= 3.0:
                mission_state = STATE_MISSION_WAITING
                red_found_time = 0.0

        elif mission_state == STATE_MISSION_WAITING:
            tbot.stop()

        # NETWORK LOGIC
        now = time.time()
        if detected_colour and detected_colour != last_sent_colour:
            has_received_confirmation = False

        if ( state == STATE_CLIENT_RUNNING ):
            if ( detected_colour and target_client and ( detected_colour != last_sent_colour or now - last_send_time >= min_send_interval ) and not has_received_confirmation ):
                state = STATE_CLIENT_SEND_COLOUR
            else:
                state = STATE_CLIENT_RECEIVE_COLOUR

        elif ( state == STATE_CLIENT_SEND_COLOUR ):
            out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': ' + detected_colour
            cs.sendall( ( out_msg + '\n' ).encode() )
            last_sent_colour = detected_colour
            last_send_time = now
            state = STATE_CLIENT_RUNNING

        elif ( state == STATE_CLIENT_RECEIVE_COLOUR ):
            try:
                chunk = cs.recv( 1024 )
                if chunk:
                    recv_buffer += chunk.decode()
                    lines = recv_buffer.split( '\n' )
                    recv_buffer = lines[-1]
                    for line in lines[:-1]:
                        server_msg_text = line.strip()
                        if server_msg_text.startswith( 'Forwarding ' + MSG_COLOUR ):
                            apply_colour_lights( server_msg_text.split(':')[-1].strip().lower() )
                        elif server_msg_text.startswith( 'Forwarding ' + MSG_RECEIVED ):
                            has_received_confirmation = True
            except socket.timeout:
                pass
            state = STATE_CLIENT_RUNNING

except KeyboardInterrupt:
    print( 'interrupted' )
finally:
    safe_cleanup( cs, picam2 )