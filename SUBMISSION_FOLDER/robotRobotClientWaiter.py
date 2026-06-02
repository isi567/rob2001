# Waiter client for robot-robot system

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

# is the robot moving?
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

# define motion functions
def go_forward(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('moving forward')
    tbot.forward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def go_backward(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('moving backward')
    tbot.backward(DRIVE_SPEED)
    time.sleep(DRIVE_TIME)
    tbot.stop()

def turn_left(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('turning left')
    tbot.curve_forward_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def turn_right(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('turning right')
    tbot.curve_forward_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_right(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('sharp right')
    tbot.turn_right(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

def sharp_left(tbot):
    if not move_enabled:
        print('movement disabled; waiting for green')
        return
    print('sharp left')
    tbot.turn_left(TURN_SPEED)
    time.sleep(TURN_TIME)
    tbot.stop()

# underlighting definitions
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

def send_status(cs, client_id, target_id, status_text):
    status_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + target_id + ': ' + status_text
    cs.sendall((status_msg + '\n').encode())
    print('[%s] sent: %s' % (client_id, status_text))

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
        print('usage: python robotRobotClientWaiter.py waiter chef')
        sys.exit(1)

    client_id = sys.argv[1]
    target_id = sys.argv[2]

    print('[%s] Starting (target: %s)' % (client_id, target_id))
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
        print('[%s] Connected to server' % client_id)

        state = 2
        last_sent_colour = None
        last_send_time = 0.0
        min_send_interval = 0.8
        recv_buffer = ''
        has_sent_colour = False
        has_received_confirmation = False
        has_sent_found = False
        has_notified_waiting = False
        last_reported_state = None

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
            
            # send "found" to target when green is detected
            if detected_colour == 'green' and target_id and not has_sent_found:
                out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': found'
                try:
                    cs.sendall((out_msg + '\n').encode())
                    print('[%s] sent: found' % client_id)
                    has_sent_found = True
                    last_send_time = now
                except Exception as e:
                    print('[%s] send error: %s' % (client_id, e))
                    break

            #set mission states
            if mission_state != last_reported_state:
                if mission_state == 10:
                    send_status(cs, client_id, target_id, 'looking for green')
                elif mission_state == 11:
                    send_status(cs, client_id, target_id, 'found green')
                elif mission_state == 12:
                    send_status(cs, client_id, target_id, 'looking for red')
                elif mission_state == 13:
                    send_status(cs, client_id, target_id, 'returning to red')
                last_reported_state = mission_state

            if mission_state == 10:  # LOOKING_FOR_GREEN
                print('[%s] looking for green...' % client_id)
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
                print('[%s] found green!' % client_id)
                mission_state = 12

            elif mission_state == 12:  # LOOKING_FOR_RED
                print('[%s] looking for red...' % client_id)
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
                print('[%s] returning to red...' % client_id)
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
                if not has_notified_waiting:
                    waiting_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + target_id + ': waiting'
                    cs.sendall((waiting_msg + '\n').encode())
                    print('[%s] sent: waiting' % client_id)
                    has_notified_waiting = True

            # check for pending messages
            pending_message = None
            try:
                pending_message = input_queue.get_nowait()
            except queue.Empty:
                pending_message = None

            if pending_message is not None and not has_sent_colour:
                client_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': ' + pending_message
                cs.sendall((client_msg + '\n').encode())
                print('[%s] sent: %s' % (client_id, pending_message))
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
                            apply_colour_lights(tbot, msg_colour)
                            # when chef's orders come throughm, allow movement
                            if msg_colour == 'green' or 'tomato' or 'cucumber':
                                move_enabled = True
                                cs.sendall('movement enabled\n'.encode())
                                mission_state = 10  
                                # reset to LOOKING_FOR_GREEN to restart the sequence
                                green_found_time = 0.0
                                red_found_time = 0.0
                                has_notified_waiting = False
                                last_reported_state = None
                                print('[%s] *** MOVEMENT ENABLED - mission restart ***' % client_id)
                            else:
                                move_enabled = False
                            # send confirmation back to sender
                            reply_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            cs.sendall((reply_msg + '\n').encode())
                elif server_msg_text.startswith(received_prefix):
                    payload = server_msg_text[len(received_prefix):]
                    if ' to ' in payload:
                        msg_from, msg_to = payload.split(' to ', 1)
                        if msg_to.strip() == client_id:
                            print('[combined %s] got received confirmation from %s' % (client_id, msg_from))
                            has_received_confirmation = True
                            has_sent_colour = False

    except KeyboardInterrupt:
        print('[%s] Interrupted by user' % client_id)
    except Exception as e:
        print('[%s] Fatal error: %s' % (client_id, e))
    finally:
        safe_cleanup(tbot, cs, picam2)

if __name__ == '__main__':
    main()
