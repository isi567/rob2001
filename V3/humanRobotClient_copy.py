# Human Robot Client

import time
import sys
import socket
import threading
import queue

# network protocol constants
MSG_REGISTER = 'REGISTER'
MSG_COLOUR = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'

#host computer IP address
HOST = 'localhost'
#HOST = '10.247.26.135'
PORT = 50007

# is robot moving?
move_enabled = False

# motion parameters
DRIVE_SPEED = 1.0
DRIVE_TIME  = 1.2
TURN_SPEED  = 0.6
TURN_TIME   = 0.6

# motion function definitions
def go_forward(tbot):
    return

def go_backward(tbot):
    return

def turn_left(tbot):
    return

def turn_right(tbot):
    return

def sharp_right(tbot):
    return

def sharp_left(tbot):
    return

# underlighting definitions
def red_lights(tbot):
    return

def green_lights(tbot):
    return

def lights_off(tbot):
    return

def apply_colour_lights(tbot, colour):
    return

def get_distance(tbot):
    return 9999

def safe_cleanup(tbot=None, sock=None):
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
                            # Acknowledge receipt only; do not send a colour reply.
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
def waiter_main(client_id, target_id, tbot, sock):
    global move_enabled
    print('[%s] WAITER (target: %s)' % (client_id, target_id))
    print('[%s] Type a message to send:' % client_id)
    
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
                        if msg_to == client_id and msg_content == 'green':
                            print('[%s] RECEIVED GREEN' % client_id)
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
                                    print('[%s] ok, fetching bill' % client_id)
                                else:
                                    print('[%s] action complete: %s' % (client_id, last_sent_text))
                                has_sent_message = False
                                last_sent_text = None

        # Phase 2: camera-free idle mode for testing
        elif phase == 2:
            time.sleep(0.05)

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
    
    tbot = None
    
    cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cs.connect((HOST, PORT))
        cs.settimeout(0.5)
        cs.sendall((MSG_REGISTER + ' ' + client_id + '\n').encode())
        print('[%s] Connected to server' % client_id)

        if role == '--waiter':
            waiter_main(client_id, target_id, tbot, cs)
        else:  # chef
            chef_main(client_id, target_id, tbot, cs)

    except KeyboardInterrupt:
        print('[%s] Interrupted by user' % client_id)
    except Exception as e:
        print('[%s] Fatal error: %s' % (client_id, e))
    finally:
        safe_cleanup(tbot, cs)

if __name__ == '__main__':
    main()
