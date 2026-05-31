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
# import trilobot package 
from trilobot import Trilobot
from picamera2 import Picamera2
# import vision package
import cv2
# import additional code -- this is where the real vision code lives.
import find

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
            'draw_color': (0, 0, 255)  # BGR format
        },
        'green': {
            'lower': np.array([40, 50, 50]),
            'upper': np.array([80, 255, 255]),
            'draw_color': (0, 255, 0)
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

# define distance sensor function
def get_distance():
    distance = tbot.read_distance()
    print( 'distance from nearest object = %fcm' % ( distance ))
    return( distance )


#-----
# main
#-----

# initialise a "tbot" object
print( 'hello!' )
tbot = Trilobot()

# start the camera
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()

while True:
    img = picam2.capture_array()

    # Find centers of largest colored areas
    centers = find.find_color_centers(img, colour_ranges)

    # Print results
    if centers.get("red") is not None:
        print("Red object at x:", centers.get("red")[0], "y: ", centers.get("red")[1])
        red_lights()
    else:
        print("No red objects found")
        lights_off()

    if centers.get("green") is not None:
        print("Green object at x:", centers.get("green")[0], "y: ", centers.get("green")[1])
        green_lights()
    else:
        print("No green objects found")
        lights_off()

    #################################################################
    #
    # This is where you make a decision based on where the centres of
    # the coloured areas are.
    #
    #################################################################

    # An initial cut at a colour-driven control process.
    #
    # If we see a green area, head towards it
    if centers.get("green") is not None:
        green_x = centers.get("green")[0]
        # Turn to face the green area. 320 should be the middle of the
        # image, so if we are close to that, then just drive, else turn
        # to reduce that.
        if green_x < 280:
            turn_left()
        elif green_x > 360:
            turn_right()
        else:
            if get_distance() < 10:
                go_backward()
            else:
                go_forward()
    elif centers.get("red") is not None:
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
    # Otherwise, look for it
    else:
        sharp_right()
