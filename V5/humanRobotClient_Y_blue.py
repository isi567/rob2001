# Human Robot Client

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

#host computer IP address
#HOST = 'localhost'
HOST = '10.247.26.135'
PORT = 50007

# is robot moving?
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
    },
    'blue': {
        'lower': np.array([100, 80, 80]),
        'upper': np.array([130, 255, 255]),
        'draw_colour': (255, 0, 0)
    }
}

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

# underlighting definitions
def red_lights(tbot):
    tbot.fill_underlighting((255,0,0))

def green_lights(tbot):
    tbot.fill_underlighting((0,255,0))

def blue_lights(tbot):
    tbot.fill_underlighting((0,0,255))

def lights_off(tbot):
    tbot.clear_underlighting()

def apply_colour_lights(tbot, colour):
    if colour == 'red':
        red_lights(tbot)
    elif colour == 'green':
        green_lights(tbot)
    elif colour == 'blue':
        blue_lights(tbot)
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


#main if client is chef
def chef_main(client_id, target_id, tbot, sock):
    global move_enabled
    print('[%s] CHEF (target: %s)' % (client_id, target_id))
    
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
                        
                        #  if the message is 'food' then chef responds green
                        if msg_colour == 'food':
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

                        if msg_colour == 'bill':
                            phase = 2
                            #activate movement loop
                            reply_conf = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            try:
                                sock.sendall((reply_conf + '\n').encode())
                            except Exception:
                                pass
                        
                        if msg_colour == 'sauce':
                            phase = 2
                            #activate movement loop
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

#main if client is waiter
def waiter_main(client_id, target_id, tbot, sock, picam2):
    global move_enabled
    print('[%s] WAITER (target: %s)' % (client_id, target_id))
    print('[%s] Type a message to send to chef:' % client_id)
    
    input_queue = queue.Queue()
    stdin_thread = threading.Thread(target=stdin_reader, args=(input_queue,), daemon=True)
    stdin_thread.start()
    
    # Wait for user input, send it, and wait for green
    # 1 = waiting for user input, 2 = lookinh for green
    phase = 1  
    has_sent_message = False
    pending_message = None
    last_sent_text = None
    
    recv_buffer = ''
    has_sent_found = False

    # STATE_MISSION_LOOKING_FOR_GREEN
    mission_state = 10  
    green_found_time = 0.0
    red_found_time = 0.0
    green_detection_threshold = 1.0

    # going to kitchen 
    mission_state = 16

    while True:
        #  Wait for user input or wait for green
        if phase == 1:
            if pending_message is None:
                try:
                    pending_message = input_queue.get_nowait()
                except queue.Empty:
                    pending_message = None
            
            # Send message
            if pending_message is not None and not has_sent_message:
                text = pending_message.strip()
                text_lower = text.lower()
                message_target = target_id

                msg_to_send = MSG_COLOUR + ' from ' + client_id + ' to ' + message_target + ': ' + text
                try:
                    sock.sendall((msg_to_send + '\n').encode())
                    print('[%s] sent: %s' % (client_id, text))
                    has_sent_message = True
                    last_sent_text = text_lower
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
                        if msg_to == client_id:
                            if msg_content == 'green':
                                # puts into go phase (2)
                                print('message content: ' + msg_content)
                                print('[%s] RECEIVED GO' % client_id)
                                move_enabled = True
                                print("____________________MOVING______________________")
                                phase = 2
                                mission_state = 10
                            elif msg_content in ('bill', 'sauce'):
                                print('message content: ' + msg_content)
                                print('[%s] RECEIVED GO' % client_id)
                                move_enabled = True
                                print("____________________MOVING______________________")
                                phase = 2
                                mission_state = 12

                            # Send confirmation
                            reply_conf = MSG_RECEIVED + ' from ' + client_id + ' to ' + msg_from
                            try:
                                sock.sendall((reply_conf + '\n').encode())
                            except Exception:
                                pass
                            break
                        # chef no longer sends a colour reply for 'bill'; waiter will handle confirmation

                elif server_msg_text.startswith(received_prefix):
                    payload = server_msg_text[len(received_prefix):]
                    if ' to ' in payload:
                        msg_from, msg_to = payload.split(' to ', 1)
                        if msg_to.strip() == client_id:
                            print('[%s] got received confirmation from %s' % (client_id, msg_from))
                            # If we previously sent a message and get a received-confirmation
                            # from the target, consider the action complete and allow sending again.
                            if last_sent_text is not None and msg_from.strip() == target_id:
                                if last_sent_text == 'bill':
                                    print('[%s] Ok, fetching bill' % client_id)
                                elif last_sent_text == 'sauce':
                                    print('[%s] Ok, fetching sauce' % client_id)
                                has_sent_message = False
                                last_sent_text = None

        # Phase 2: Run movement colour finding code
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
                print("Red Detected")
            else:
                lights_off(tbot)

            if centers.get('green') is not None:
                apply_colour_lights(tbot, 'green')
                detected_colour = 'green'
                print("Green Detected")
            else:
                lights_off(tbot)

            if centers.get('blue') is not None:
                apply_colour_lights(tbot, 'blue')
                detected_colour = 'blue'
                print("Blue Detected")
            else:
                lights_off(tbot)

            now = time.time()

            # send "found" to chef when green is detected
            if detected_colour == 'green' and target_id and not has_sent_found:
                out_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + target_id + ': found'
                try:
                    sock.sendall((out_msg + '\n').encode())
                    print('[%s] sent: found' % client_id)
                    has_sent_found = True
                except Exception as e:
                    print('[%s] send error: %s' % (client_id, e))
                    break

            # LOOKING_FOR_GREEN
            if mission_state == 10:
                print("Looking for green")
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

             # if LOOKING_FOR_BLUE
            elif mission_state == 15:  
                print("Looking for blue")
                if centers.get('blue') is not None:
                    blue_x = centers.get('blue')[0]
                    now_check = time.time()
                    if blue_found_time == 0.0:
                        blue_found_time = now_check
                    if now_check - blue_found_time >= green_detection_threshold:
                        mission_state = 16
                        red_found_time = 0.0
                    else:
                        if blue_x < 280:
                            turn_left(tbot)
                        elif blue_x > 360:
                            turn_right(tbot)
                        else:
                            if get_distance(tbot) < 10:
                                go_backward(tbot)
                            else:
                                go_forward(tbot)
                else:
                    blue_found_time = 0.0
                    sharp_right(tbot)


            # if RETURN_TO_BLUE
            elif mission_state == 16:  
                print("going to blue")
                if centers.get('blue') is not None:
                    blue_x = centers.get('blue')[0]
                    if blue_x < 280:
                        turn_left(tbot)
                    elif blue_x > 360:
                        turn_right(tbot)
                    else:
                        if get_distance(tbot) < 10:
                            go_backward(tbot)
                        else:
                            go_forward(tbot)
                else:
                    sharp_right(tbot)
                
                now_check = time.time()
                if blue_found_time == 0.0:
                    blue_found_time = now_check
                if now_check - blue_found_time >= 3.0:
                    print('[%s] At blue location (resteraunt)' % client_id)
                    mission_state = 14
                    red_found_time = 0.0
                    move_enabled = False


            # if FOUND_GREEN
            elif mission_state == 11:
                mission_state = 12

            # if LOOKING_FOR_RED
            elif mission_state == 12:
                print("Looking for red")
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

            # if RETURN_TO_RED
            elif mission_state == 13:
                print("going to red")
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
                    print('[%s] At red location (kitchen)' % client_id)
                    # if looking for bill or sauce, it needs to look for blue instead of red next, so set state accordingly
                    if last_sent_text in ('bill', 'sauce'):
                         mission_state = 15
                    else:
                        mission_state = 14
                    red_found_time = 0.0
                    move_enabled = False

            # if WAITING
            elif mission_state == 14:
                print("Stopping")
                tbot.stop()

            # if bill or sauce, find red and then find blue
            elif mission_state == 17:
                mission_state = 12


            # Receive messages
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
        print('if you want to be a waiter, type arguments: Waiter Chef --waiter')
        print('if you want to be a chef, type arguments: Chef Waiter --chef')
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
    picam2 = None
    try:
        cs.connect((HOST, PORT))
        cs.settimeout(0.5)
        cs.sendall((MSG_REGISTER + ' ' + client_id + '\n').encode())
        print('[%s] Connected to server' % client_id)

        if role == '--waiter':
            picam2 = Picamera2()
            picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
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
