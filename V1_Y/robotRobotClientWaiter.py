#!/usr/bin/env python3
"""
Combined client: merges vision + Trilobot control from trilo_vision_mimi_2.py
with messaging/interactive behaviour from robocolorClient2.py.

Usage: python combinedclient2.py <ID> <TARGET_ID>
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

HOST = '10.247.26.135'
PORT = 50007

# globals for forwarding messages to the chef via server
cs_global = None
client_id_global = None
chef_id_global = None


def send_to_chef(msg, from_id=None, to_id=None):
    """Send a MESSAGE to the chef via the server. Falls back to local print().

    If `from_id` or `to_id` are provided they override the globals (useful
    before the socket is connected).
    """
    global cs_global, client_id_global, chef_id_global
    out_from = from_id if from_id is not None else (client_id_global or 'unknown')
    out_to = to_id if to_id is not None else (chef_id_global or 'chef')
    out_msg = MSG_COLOUR + ' from ' + str(out_from) + ' to ' + str(out_to) + ': ' + str(msg)
    if cs_global is not None:
        try:
            cs_global.sendall((out_msg + '\n').encode())
            return
        except Exception:
            pass
    print(out_msg)


def handle_chef_message(tbot, message_text):
    """React to chef status and ingredient messages differently.

    Returns an actions dict which may contain keys:
    - 'mission_state': int to set mission_state
    - 'move_enabled': bool to set move_enabled
    - 'stop': True to call tbot.stop()
    """
    actions = {}
    normalized = message_text.strip().lower()

    if normalized.startswith('asking for '):
        ingredient = normalized[len('asking for '):].strip()
        send_to_chef('chef status: asking for %s' % ingredient)
        # switch mission state to search for the requested ingredient
        if ingredient == 'tomato':
            actions['mission_state'] = 12  # LOOKING_FOR_RED
            actions['move_enabled'] = True
        elif ingredient == 'cucumber' or ingredient == 'green':
            actions['mission_state'] = 10  # LOOKING_FOR_GREEN
            actions['move_enabled'] = True
        return actions

    if normalized == 'green':
        send_to_chef('chef ingredient: green')
        apply_colour_lights(tbot, 'green')
        actions['move_enabled'] = True
        actions['mission_state'] = 10
        return actions

    if normalized == 'tomato':
        send_to_chef('chef ingredient: tomato')
        apply_colour_lights(tbot, 'red')
        # when ingredient received, stop moving
        actions['move_enabled'] = False
        actions['stop'] = True
        return actions

    if normalized == 'cucumber':
        send_to_chef('chef ingredient: cucumber')
        apply_colour_lights(tbot, 'green')
        actions['move_enabled'] = False
        actions['stop'] = True
        return actions

    if normalized == 'saying food made':
        send_to_chef('chef status: food made')
        return actions

    if normalized == 'food made':
        send_to_chef('chef action: food made')
        actions['move_enabled'] = False
        actions['stop'] = True
        return actions

    send_to_chef('chef message: %s' % normalized)
    return actions

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
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('moving forward')
    tbot.forward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def go_backward(tbot):
    if not move_enabled:
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('moving backward')
    tbot.backward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def turn_left(tbot):
    if not move_enabled:
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('turning left')
    tbot.curve_forward_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def turn_right(tbot):
    if not move_enabled:
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('turning right')
    tbot.curve_forward_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_right(tbot):
    if not move_enabled:
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('sharp right')
    tbot.turn_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_left(tbot):
    if not move_enabled:
        send_to_chef('movement disabled; waiting for green')
        return
    #send_to_chef('sharp left')
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

def main():
    global move_enabled
    if len(sys.argv) < 3:
        print('usage: python combinedclient2.py <ID> <TARGET_ID>', from_id='unknown', to_id='chef')
        sys.exit(1)

    client_id = sys.argv[1]
    target_id = sys.argv[2]

    #print('[%s] Starting (target: %s)' % (client_id, target_id), from_id=client_id, to_id=target_id)
    tbot = Trilobot()

    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"size": (640,480)}))
    picam2.start()

    input_queue = queue.Queue()
    stdin_thread = threading.Thread(target=stdin_reader, args=(input_queue,), daemon=True)
    stdin_thread.start()

    cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cs.connect((HOST, PORT))
        cs.settimeout(0.5)
        cs.sendall((MSG_REGISTER + ' ' + client_id + '\n').encode())
        # set globals used by send_to_chef so subsequent calls forward to chef
        global cs_global, client_id_global, chef_id_global
        cs_global = cs
        client_id_global = client_id
        chef_id_global = target_id
        print('[%s] Connected to server' % client_id)

        state = 2
        last_sent_colour = None
        last_send_time = 0.0
        min_send_interval = 0.8
        recv_buffer = ''
        has_sent_colour = False
        has_received_confirmation = False
        has_sent_found = False  # Track "found" detection - only sent once per interaction

        mission_state = 10  # STATE_MISSION_LOOKING_FOR_GREEN
        green_found_time = 0.0
        red_found_time = 0.0
        green_detection_threshold = 1.0

        while True:
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
                    cs.sendall((out_msg + '\n').encode())
                    send_to_chef('sent: found')
                    has_sent_found = True
                    last_send_time = now
                except Exception as e:
                    send_to_chef('send error: %s' % (e,))
                    break

            #################################################################
            # Control logic based on mission state machine
            #################################################################
            if mission_state == 10:  # LOOKING_FOR_GREEN
                send_to_chef('Looking for green')
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
                send_to_chef('Looking for red')
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
                send_to_chef('Going to red')
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
                    send_to_chef('Mission complete - at red location')
                    mission_state = 14
                    red_found_time = 0.0
                    move_enabled = False  # Stop moving when mission complete

            elif mission_state == 14:  # WAITING
                #send_to_chef('Stopping')
                tbot.stop()

            # check for interactive input to send arbitrary messages
            pending_message = None
            try:
                pending_message = input_queue.get_nowait()
            except queue.Empty:
                pending_message = None

            if pending_message is not None and not has_sent_colour:
                client_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': ' + pending_message
                cs.sendall((client_msg + '\n').encode())
                print('sent: %s' % (pending_message,))
                has_sent_colour = True
                has_received_confirmation = False

            # receive and handle server messages
            try:
                chunk = cs.recv(1024)
            except socket.timeout:
                time.sleep(0.01)
                continue
            except OSError:
                break

            if not chunk:
                print('Server disconnected')
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
                            send_to_chef('received from %s: %s' % (msg_from, msg_colour))
                            actions = handle_chef_message(tbot, msg_colour)
                            if actions is None:
                                actions = {}
                            if 'mission_state' in actions:
                                mission_state = actions['mission_state']
                            if 'move_enabled' in actions:
                                move_enabled = actions['move_enabled']
                                if move_enabled:
                                    send_to_chef('*** MOVEMENT ENABLED - mission restart ***')
                            if actions.get('stop'):
                                try:
                                    tbot.stop()
                                except Exception:
                                    pass
                            # send confirmation back to sender
                            reply_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            cs.sendall((reply_msg + '\n').encode())
                elif server_msg_text.startswith(received_prefix):
                    payload = server_msg_text[len(received_prefix):]
                    if ' to ' in payload:
                        msg_from, msg_to = payload.split(' to ', 1)
                        if msg_to.strip() == client_id:
                            print('got received confirmation from %s' % (msg_from,))
                            has_received_confirmation = True
                            has_sent_colour = False

    except KeyboardInterrupt:
        print('Interrupted by user', from_id=client_id)
    except Exception as e:
        print('Fatal error: %s' % (e,), from_id=client_id)
    finally:
        safe_cleanup(tbot, cs, picam2)

if __name__ == '__main__':
    main()
