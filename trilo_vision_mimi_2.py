#!/usr/bin/env python3
#
# trilo_vision.py
#
# This is an extension of the tri1.py trilobot driving code to
# incorporate vision running headless on the trilobot (based on
# trilo_blob.py)
#
# tri1.py is due to
# esklar/16-feb-2024
# University of Lincoln
#
# and the rest was written by
#
# Simon Parsons
# University of Lincoln
# 26-03-13
#

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
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_SEND_COLOUR    = 4
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
            'lower': np.array([100, 50, 50]),
            'upper': np.array([130, 255, 255]),
            'draw_colour': (0, 0, 255)  # BGR format
        },
        'green': {
            'lower': np.array([40, 50, 50]),
            'upper': np.array([80, 255, 255]),
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

def turn_left():
    print( 'turning left' )
    tbot.curve_forward_left( TURN_SPEED )
    time.sleep( TURN_TIME )
    tbot.stop()

def sharp_right():
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
    # Best-effort shutdown to avoid GPIO/PWM cleanup errors on exit.
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
    print( 'usage: python "trilo_vision (1).py" <ID> <TARGET_ID> [HOST] [PORT]' )
    sys.exit( 1 )

client_id = sys.argv[1]
target_client = sys.argv[2]
server_host = HOST
server_port = PORT
if ( len( sys.argv ) >= 4 ):
    server_host = sys.argv[3]
if ( len( sys.argv ) >= 5 ):
    server_port = int( sys.argv[4] )

# initialise a "tbot" object
print( 'hello!' )
tbot = Trilobot()

# start the camera
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()

# connect to server and register this Trilobot client
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
        else:
            print( '[vision %s] no register reply (continuing)' % ( client_id ))
    except socket.timeout:
        # Server may not reply to REGISTER; continue running.
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
    green_detection_threshold = 1.0  # seconds to confirm detection

    while True:
        img = picam2.capture_array()

        # Find centers of largest coloured areas
        centers = find.find_color_centers(img, colour_ranges)

        detected_colour = None

        # Print results
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

        # send detected colour updates to target robot via server
        now = time.time()
        # if we detect a new colour, allow sending again (clear confirmation)
        if detected_colour and detected_colour != last_sent_colour:
            has_received_confirmation = False

        if ( detected_colour and target_client and ( detected_colour != last_sent_colour or now - last_send_time >= min_send_interval ) ):
            out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': ' + detected_colour
            try:
                cs.sendall( (out_msg + '\n').encode() )
                print( '[vision %s] sent: %s' % ( client_id, out_msg ))
                last_sent_colour = detected_colour
                last_send_time = now
            except Exception as e:
                print( '[vision %s] send error: %s' % ( client_id, e ))
                break

    #################################################################
    #
    # Control logic based on mission state machine
    #
    #################################################################

        if mission_state == STATE_MISSION_LOOKING_FOR_GREEN:
            # Search for green - turn/drive toward it
            if centers.get("green") is not None:
                green_x = centers.get("green")[0]
                now = time.time()
                if green_found_time == 0.0:
                    green_found_time = now
                # Check if we've confirmed green for threshold time
                if now - green_found_time >= green_detection_threshold:
                    print('[vision %s] Found green, moving to FOUND_GREEN state' % (client_id))
                    mission_state = STATE_MISSION_FOUND_GREEN
                    green_found_time = 0.0
                else:
                    # Still confirming - move toward green
                    if green_x < 280:
                        turn_left()
                    elif green_x > 360:
                        turn_right()
                    else:
                        if get_distance() < 10:
                            go_backward()
                        else:
                            go_forward()
            else:
                # No green found - keep searching
                green_found_time = 0.0
                sharp_right()

        elif mission_state == STATE_MISSION_FOUND_GREEN:
            # Send message that we found green
            out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': green_found'
            try:
                cs.sendall( (out_msg + '\n').encode() )
                print( '[vision %s] sent: %s' % ( client_id, out_msg ))
                mission_state = STATE_MISSION_LOOKING_FOR_RED
            except Exception as e:
                print( '[vision %s] send error: %s' % ( client_id, e ))
                break

        elif mission_state == STATE_MISSION_LOOKING_FOR_RED:
            # Search for red - turn/drive toward it
            if centers.get("red") is not None:
                red_x = centers.get("red")[0]
                now = time.time()
                if red_found_time == 0.0:
                    red_found_time = now
                # Check if we've confirmed red for threshold time
                if now - red_found_time >= green_detection_threshold:
                    print('[vision %s] Found red, moving to RETURN_TO_RED state' % (client_id))
                    mission_state = STATE_MISSION_RETURN_TO_RED
                    red_found_time = 0.0
                else:
                    # Still confirming - move toward red
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
                # No red found - keep searching
                red_found_time = 0.0
                sharp_right()

        elif mission_state == STATE_MISSION_RETURN_TO_RED:
            # Continue moving toward red
            if centers.get("red") is not None:
                red_x = centers.get("red")[0]
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
                # Lost red - search for it again
                sharp_right()
            
            # Check if we've been with red long enough, then wait
            now = time.time()
            if red_found_time == 0.0:
                red_found_time = now
            if now - red_found_time >= 3.0:  # Wait 3 seconds with red before moving to waiting state
                print('[vision %s] At red location, moving to WAITING state' % (client_id))
                mission_state = STATE_MISSION_WAITING
                red_found_time = 0.0

        elif mission_state == STATE_MISSION_WAITING:
            # Wait for new instructions - stop moving
            tbot.stop()
            print('[vision %s] Waiting for new instructions' % (client_id))

        now = time.time()
        if ( state == STATE_CLIENT_RUNNING ):
            if ( detected_colour and target_client and ( detected_colour != last_sent_colour or now - last_send_time >= min_send_interval ) and not has_received_confirmation ):
                state = STATE_CLIENT_SEND_COLOUR
            else:
                state = STATE_CLIENT_RECEIVE_COLOUR

        elif ( state == STATE_CLIENT_SEND_COLOUR ):
            out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_client + ': ' + detected_colour
            try:
                cs.sendall( ( out_msg + '\n' ).encode() )
                print( '[vision %s] sent: %s' % ( client_id, out_msg ))
                last_sent_colour = detected_colour
                last_send_time = now
            except Exception as e:
                print( '[vision %s] send error: %s' % ( client_id, e ))
                break
            state = STATE_CLIENT_RUNNING

        elif ( state == STATE_CLIENT_RECEIVE_COLOUR ):
            try:
                chunk = cs.recv( 1024 )
            except socket.timeout:
                state = STATE_CLIENT_RUNNING
                continue
            except OSError:
                state = STATE_CLIENT_EXITING
                continue

            if ( not chunk ):
                print( '[vision %s] server disconnected' % ( client_id ))
                state = STATE_CLIENT_EXITING
                continue

            recv_buffer += chunk.decode()
            lines = recv_buffer.split( '\n' )
            recv_buffer = lines[-1]

            for line in lines[:-1]:
                server_msg_text = line.strip()
                if ( not server_msg_text ):
                    continue

                print( '[vision %s] received: %s' % ( client_id, server_msg_text ))
                colour_prefix = 'Forwarding ' + MSG_COLOUR + ' from '
                received_prefix = 'Forwarding ' + MSG_RECEIVED + ' from '

                if ( server_msg_text.startswith( colour_prefix ) ):
                    payload = server_msg_text[ len( colour_prefix ): ]
                    if ( ' to ' in payload and ':' in payload ):
                        msg_from, remainder = payload.split( ' to ', 1 )
                        msg_to_text, msg_colour = remainder.split( ':', 1 )
                        msg_to = msg_to_text.strip()
                        msg_colour = msg_colour.strip().lower()
                        if ( msg_to == client_id ):
                            print( '[vision %s] peer %s colour: %s' % ( client_id, msg_from, msg_colour ))
                            apply_colour_lights( msg_colour )
                            reply_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            cs.sendall( ( reply_msg + '\n' ).encode() )
                            print( '[vision %s] sent: %s' % ( client_id, reply_msg ))
                elif ( server_msg_text.startswith( received_prefix ) ):
                    payload = server_msg_text[ len( received_prefix ): ]
                    if ( ' to ' in payload ):
                        msg_from, msg_to = payload.split( ' to ', 1 )
                        if ( msg_to.strip() == client_id ):
                            print( '[vision %s] got received confirmation from %s' % ( client_id, msg_from ))
                            has_received_confirmation = True

            state = STATE_CLIENT_RUNNING
except KeyboardInterrupt:
    print( '[vision %s] interrupted by user' % ( client_id ))
except Exception as e:
    print( '[vision %s] fatal error: %s' % ( client_id, e ))
finally:
    safe_cleanup( cs, picam2 )
