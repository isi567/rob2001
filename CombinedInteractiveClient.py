#!/usr/bin/env python3
"""
Combined Interactive Client: merges message-based interaction (waiter sends food, 
chef responds with green) with vision and robot movement (combinedclient2 functionality).

WAITER role: sends "food", receives "green", then executes combinedclient2 mission
CHEF role: receives messages, responds with "green"

Usage:
  WAITER: python CombinedInteractiveClient.py <ID> <TARGET_ID> --waiter
  CHEF:   python CombinedInteractiveClient.py <ID> <TARGET_ID> --chef
"""

import time
import sys
import socket
import threading
import queue
import numpy as np
import cv2
from trilobot import Trilobot
from picamera2 import Picamera2
import find

# network protocol constants
MSG_REGISTER = 'REGISTER'
MSG_COLOUR = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'

HOST = '10.247.72.17'
PORT = 50007

# movement gating: robot will not actuate motors unless this is True
move_enabled = False

# motion parameters
DRIVE_SPEED = 1.0
DRIVE_TIME  = 1.2
TURN_SPEED  = 0.6
TURN_TIME   = 0.6

# colour thresholds (HSV)
colour_ranges = {
    'red': {
        'lower': np.array([0, 120, 120]),
        'upper': np.array([10, 255, 255]),
        'draw_colour': (0, 0, 255)
    },
    'green': {
        'lower': np.array([50, 80, 80]),
        'upper': np.array([70, 255, 255]),
        'draw_colour': (0, 255, 0)
    }
}

# define motion functions (guarded by move_enabled)
def go_forward(tbot):
    if not move_enabled:
        return
    print('moving forward')
    tbot.forward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def go_backward(tbot):
    if not move_enabled:
        return
    print('moving backward')
    tbot.backward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def turn_left(tbot):
    if not move_enabled:
        return
    print('turning left')
    tbot.curve_forward_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def turn_right(tbot):
    if not move_enabled:
        return
    print('turning right')
    tbot.curve_forward_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_right(tbot):
    if not move_enabled:
        return
    print('sharp right')
    tbot.turn_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_left(tbot):
    if not move_enabled:
        return
    print('sharp left')
    tbot.turn_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

# underlighting helpers
def red_lights(tbot):
    tbot.fill_underlighting((255,0,0))

def green_lights(tbot):
    tbot.fill_underlighting((0,255,0))

def lights_off(tbot):
    tbot.clear_underlighting()

def apply_colour_lights(tbot, colour):
    if colour == 'red':
        red_lights(tbot)
    elif colour == 'green':
        green_lights(tbot)
    else:
        lights_off(tbot)

def get_distance(tbot):
    return tbot.read_distance()

def safe_cleanup(tbot=None, sock=None, camera=None):
    try:
        if tbot is not None:
            tbot.stop()
    except Exception:
        pass
    try:
        if tbot is not None:
            tbot.clear_underlighting()
    except Exception:
        pass
    try:
        if camera is not None:
            camera.stop()
    except Exception:
        pass
    try:
        if sock is not None:
            sock.close()
    except Exception:
        pass

def stdin_reader(q):
    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:
            break
        line = line.strip()
        if line:
            q.put(line)

def chef_main(client_id, target_id, tbot, sock):
    """
    CHEF mode: receive messages and respond with 'green'
    """
    global move_enabled
    print('[%s] Running in CHEF mode (target: %s)' % (client_id, target_id))
    
    recv_buffer = ''
    
    while True:
        try:
            chunk = sock.recv(1024)
        except socket.timeout:
            time.sleep(0.01)
            continue
        except OSError:
            break

        if not chunk:
            print('[%s] Server disconnected' % client_id)
            break

        recv_buffer += chunk.decode()
        lines = recv_buffer.split('\n')
        recv_buffer = lines[-1]

        for line in lines[:-1]:
            server_msg_text = line.strip()
            if not server_msg_text:
                continue
            colour_prefix = 'Forwarding ' + MSG_COLOUR + ' from '
            received_prefix = 'Forwarding ' + MSG_RECEIVED + ' from '

            if server_msg_text.startswith(colour_prefix):
                payload = server_msg_text[len(colour_prefix):]
                if ' to ' in payload and ':' in payload:
                    msg_from, remainder = payload.split(' to ', 1)
                    msg_to_text, msg_colour = remainder.split(':', 1)
                    msg_to = msg_to_text.strip()
                    msg_colour = msg_colour.strip().lower()
                    if msg_to == client_id:
                        print('[%s] received from %s: %s' % (client_id, msg_from, msg_colour))
                        
                        # Chef responds to any message with "green"
                        reply_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + msg_from + ': green'
                        try:
                            sock.sendall((reply_msg + '\n').encode())
                            print('[%s] sent: green' % client_id)
                        except Exception as e:
                            print('[%s] send error: %s' % (client_id, e))
                            break
                        
                        # Also send confirmation
                        reply_conf = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                        try:
                            sock.sendall((reply_conf + '\n').encode())
                        except Exception:
                            pass

            elif server_msg_text.startswith(received_prefix):
                payload = server_msg_text[len(received_prefix):]
                if ' to ' in payload:
                    msg_from, msg_to = payload.split(' to ', 1)
                    if msg_to.strip() == client_id:
                        print('[%s] got received confirmation from %s' % (client_id, msg_from))

def waiter_main(client_id, target_id, tbot, sock, picam2):
    """
    WAITER mode: type message, wait for green response, then run combinedclient2 mission
    """
    global move_enabled
    print('[%s] Running in WAITER mode (target: %s)' % (client_id, target_id))
    print('[%s] Type a message (e.g., "food") to send to the chef:' % client_id)
    
    input_queue = queue.Queue()
    stdin_thread = threading.Thread(target=stdin_reader, args=(input_queue,), daemon=True)
    stdin_thread.start()
    
    # Phase 1: Wait for user input, send it, and wait for green
    phase = 1  # 1 = waiting for user input, 2 = running mission
    has_sent_message = False
    pending_message = None
    
    recv_buffer = ''
    has_sent_found = False
    
    mission_state = 10  # STATE_MISSION_LOOKING_FOR_GREEN
    green_found_time = 0.0
    red_found_time = 0.0
    green_detection_threshold = 1.0

    while True:
        # Phase 1: Wait for user input and then wait for green
        if phase == 1:
            # Check for user input
            if pending_message is None:
                try:
                    pending_message = input_queue.get_nowait()
                except queue.Empty:
                    pending_message = None
            
            # Send user's message once
            if pending_message is not None and not has_sent_message:
                msg_to_send = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': ' + pending_message
                try:
                    sock.sendall((msg_to_send + '\n').encode())
                    print('[%s] sent: %s' % (client_id, pending_message))
                    has_sent_message = True
                    pending_message = None
                except Exception as e:
                    print('[%s] send error: %s' % (client_id, e))
                    break

            # Check for responses
            try:
                chunk = sock.recv(1024)
            except socket.timeout:
                time.sleep(0.01)
                continue
            except OSError:
                break

            if not chunk:
                print('[%s] Server disconnected' % client_id)
                break

            recv_buffer += chunk.decode()
            lines = recv_buffer.split('\n')
            recv_buffer = lines[-1]

            for line in lines[:-1]:
                server_msg_text = line.strip()
                if not server_msg_text:
                    continue
                colour_prefix = 'Forwarding ' + MSG_COLOUR + ' from '
                received_prefix = 'Forwarding ' + MSG_RECEIVED + ' from '

                if server_msg_text.startswith(colour_prefix):
                    payload = server_msg_text[len(colour_prefix):]
                    if ' to ' in payload and ':' in payload:
                        msg_from, remainder = payload.split(' to ', 1)
                        msg_to_text, msg_content = remainder.split(':', 1)
                        msg_to = msg_to_text.strip()
                        msg_content = msg_content.strip().lower()
                        if msg_to == client_id and msg_content == 'green':
                            print('[%s] *** RECEIVED GREEN - ENABLING MOVEMENT AND STARTING MISSION ***' % client_id)
                            move_enabled = True
                            phase = 2
                            mission_state = 10
                            
                            # Send confirmation
                            reply_conf = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            try:
                                sock.sendall((reply_conf + '\n').encode())
                            except Exception:
                                pass
                            break

                elif server_msg_text.startswith(received_prefix):
                    payload = server_msg_text[len(received_prefix):]
                    if ' to ' in payload:
                        msg_from, msg_to = payload.split(' to ', 1)
                        if msg_to.strip() == client_id:
                            print('[%s] got received confirmation from %s' % (client_id, msg_from))

        # Phase 2: Run combinedclient2 mission logic
        elif phase == 2:
            # capture image and find colours
            img = picam2.capture_array()
            try:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            except Exception:
                img_bgr = img

            centers = find.find_color_centers(img_bgr, colour_ranges)
            detected_colour = None
            if centers.get('red') is not None:
                apply_colour_lights(tbot, 'red')
                detected_colour = 'red'
            else:
                lights_off(tbot)

            if centers.get('green') is not None:
                apply_colour_lights(tbot, 'green')
                detected_colour = 'green'
            else:
                lights_off(tbot)

            now = time.time()
            
            # send "found" to target when green is detected (only once per interaction)
            if detected_colour == 'green' and target_id and not has_sent_found:
                out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': found'
                try:
                    sock.sendall((out_msg + '\n').encode())
                    print('[%s] sent: found' % client_id)
                    has_sent_found = True
                except Exception as e:
                    print('[%s] send error: %s' % (client_id, e))
                    break

            # Control logic based on mission state machine
            if mission_state == 10:  # LOOKING_FOR_GREEN
                if centers.get('green') is not None:
                    green_x = centers.get('green')[0]
                    distance = get_distance(tbot)
                    if green_x < 280:
                        turn_left(tbot)
                    elif green_x > 360:
                        turn_right(tbot)
                    else:
                        if distance < 15:
                            tbot.stop()
                            mission_state = 11
                        else:
                            go_forward(tbot)
                else:
                    sharp_right(tbot)

            elif mission_state == 11:  # FOUND_GREEN
                mission_state = 12

            elif mission_state == 12:  # LOOKING_FOR_RED
                if centers.get('red') is not None:
                    red_x = centers.get('red')[0]
                    now_check = time.time()
                    if red_found_time == 0.0:
                        red_found_time = now_check
                    if now_check - red_found_time >= green_detection_threshold:
                        mission_state = 13
                        red_found_time = 0.0
                    else:
                        if red_x < 280:
                            turn_left(tbot)
                        elif red_x > 360:
                            turn_right(tbot)
                        else:
                            if get_distance(tbot) < 10:
                                go_backward(tbot)
                            else:
                                go_forward(tbot)
                else:
                    red_found_time = 0.0
                    sharp_right(tbot)

            elif mission_state == 13:  # RETURN_TO_RED
                if centers.get('red') is not None:
                    red_x = centers.get('red')[0]
                    if red_x < 280:
                        turn_left(tbot)
                    elif red_x > 360:
                        turn_right(tbot)
                    else:
                        if get_distance(tbot) < 10:
                            go_backward(tbot)
                        else:
                            go_forward(tbot)
                else:
                    sharp_right(tbot)
                
                now_check = time.time()
                if red_found_time == 0.0:
                    red_found_time = now_check
                if now_check - red_found_time >= 3.0:
                    print('[%s] Mission complete - at red location' % client_id)
                    mission_state = 14
                    red_found_time = 0.0
                    move_enabled = False

            elif mission_state == 14:  # WAITING
                tbot.stop()

            # Receive messages during mission
            try:
                chunk = sock.recv(1024)
            except socket.timeout:
                time.sleep(0.01)
                continue
            except OSError:
                break

            if not chunk:
                print('[%s] Server disconnected' % client_id)
                break

            recv_buffer += chunk.decode()
            lines = recv_buffer.split('\n')
            recv_buffer = lines[-1]

            for line in lines[:-1]:
                server_msg_text = line.strip()
                if not server_msg_text:
                    continue
                colour_prefix = 'Forwarding ' + MSG_COLOUR + ' from '
                received_prefix = 'Forwarding ' + MSG_RECEIVED + ' from '

                if server_msg_text.startswith(colour_prefix):
                    payload = server_msg_text[len(colour_prefix):]
                    if ' to ' in payload and ':' in payload:
                        msg_from, remainder = payload.split(' to ', 1)
                        msg_to_text, msg_content = remainder.split(':', 1)
                        msg_to = msg_to_text.strip()
                        msg_content = msg_content.strip().lower()
                        if msg_to == client_id:
                            print('[%s] received from %s: %s' % (client_id, msg_from, msg_content))

                elif server_msg_text.startswith(received_prefix):
                    payload = server_msg_text[len(received_prefix):]
                    if ' to ' in payload:
                        msg_from, msg_to = payload.split(' to ', 1)
                        if msg_to.strip() == client_id:
                            print('[%s] got received confirmation from %s' % (client_id, msg_from))

def main():
    if len(sys.argv) < 4:
        print('usage: python CombinedInteractiveClient.py <ID> <TARGET_ID> --waiter')
        print('       python CombinedInteractiveClient.py <ID> <TARGET_ID> --chef')
        sys.exit(1)

    client_id = sys.argv[1]
    target_id = sys.argv[2]
    role = sys.argv[3].lower()

    if role not in ['--waiter', '--chef']:
        print('error: role must be --waiter or --chef')
        sys.exit(1)

    print('[%s] Starting (%s mode, target: %s)' % (client_id, role, target_id))
    
    tbot = Trilobot()
    
    cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cs.connect((HOST, PORT))
        cs.settimeout(0.5)
        cs.sendall((MSG_REGISTER + ' ' + client_id + '\n').encode())
        print('[%s] Connected to server' % client_id)

        picam2 = None
        if role == '--waiter':
            picam2 = Picamera2()
            picam2.configure(picam2.create_preview_configuration(main={"size": (640,480)}))
            picam2.start()
            waiter_main(client_id, target_id, tbot, cs, picam2)
        else:  # chef
            chef_main(client_id, target_id, tbot, cs)

    except KeyboardInterrupt:
        print('[%s] Interrupted by user' % client_id)
    except Exception as e:
        print('[%s] Fatal error: %s' % (client_id, e))
    finally:
        safe_cleanup(tbot, cs, picam2)

if __name__ == '__main__':
    main()
