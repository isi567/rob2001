#--
# roboclient1.py
#
# Example multi-robot system client programme
# from: https://docs.python.org/3/library/socket.html
# with comments and debugging prints by esklar/11-feb-2025
# based on esklar/echoclient4.py (mar-2026)
#
# $ python roboclient1.py < ID >
# where ID is the client ID, a string that identifies the client to the server
#
#--

# import python socket-handling library.
import socket
import sys
import time
import threading
import queue


# define the IP address of the machine on which the server is running--where you want this client to connect.
# this could be a dotted quad address or 'localhost' (shorthand for the local machine).
HOST = '10.247.72.18'   # or, e.g. '10.5.24.62'

# define the port for connecting to server.
# the value needs to match what the server used when it was initialised.
PORT = 50007

# define messages
MSG_REGISTER = 'REGISTER'
MSG_SENT = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_SEND_COLOUR    = 4
STATE_CLIENT_RECEIVE_COLOUR = 5

# client ID and target ID are command line arguments
if ( len( sys.argv ) < 3 ):
    print( 'usage: python robocolorClient.py <ID> <TARGET_ID> [MESSAGE ...]' )
    sys.exit( 1 )

client_id = sys.argv[1]
target_id = sys.argv[2]
# initial message_text may be provided on the command line, but by default
# we'll accept interactive typing after the client has started.
initial_message = ' '.join( sys.argv[3:] ).strip()
message_text = ''
input_queue = queue.Queue()

def stdin_reader(q):
    # Blocking read from stdin (one line at a time). Runs in a daemon thread.
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


# try to create and open a new socket object (called "cs", for client socket).
with socket.socket( socket.AF_INET, socket.SOCK_STREAM ) as cs:
    state = STATE_CLIENT_STARTING
    has_sent_colour = False
    has_received_confirmation = False
    last_send_time = 0.0
    send_interval = 1.0
    print( '[client %s] socket created' % ( client_id ))
    # bind the newly created socket object to the server's host and port (defined by the server).
    cs.connect(( HOST, PORT ))
    cs.settimeout( 0.5 )
    print( '[client %s] socket connected to host [%s], port [%s]' % ( client_id, HOST, PORT ))
    #state = STATE_CLIENT_RUNNING
    client_msg = MSG_REGISTER + ' ' + client_id
    print( '[client %s] sending message: %s' % ( client_id, client_msg ))
    cs.sendall( (client_msg + '\n').encode() ) # send formatted message to server
    print( '[client %s] sent message: %s' % ( client_id, client_msg ))
    state = STATE_CLIENT_RUNNING
    # start stdin reader thread to accept interactive typing after startup
    stdin_thread = threading.Thread(target=stdin_reader, args=(input_queue,), daemon=True)
    stdin_thread.start()
    # if an initial message was provided on the command line, queue it once
    if initial_message:
        input_queue.put(initial_message)
        initial_message = ''
    pending_message = None
    while( True ):



        if ( state == STATE_CLIENT_RUNNING ):
            # check for a new typed message
            if pending_message is None:
                try:
                    pending_message = input_queue.get_nowait()
                except queue.Empty:
                    pending_message = None
            # if we have a pending message that hasn't been sent yet, send it
            if ( pending_message is not None ) and ( not has_sent_colour ):
                message_text = pending_message
                state = STATE_CLIENT_SEND_COLOUR
            else:
                state = STATE_CLIENT_RECEIVE_COLOUR


        elif ( state == STATE_CLIENT_SEND_COLOUR ): # send pending message to target
            client_msg = MSG_SENT + ' from ' + client_id + ' to ' + target_id + ': ' + message_text
            cs.sendall( (client_msg + '\n').encode() ) # send formatted message to server
            print( '[client %s] sent message: %s' % ( client_id, client_msg ))
            has_sent_colour = True
            last_send_time = time.time()
            state = STATE_CLIENT_RUNNING





        elif ( state == STATE_CLIENT_ERROR ):
            state = STATE_CLIENT_EXITING
            print( '[client %s] exiting in error state' % ( client_id ))
        



        elif ( state == STATE_CLIENT_RECEIVE_COLOUR ):
            try:
                server_msg = cs.recv( 1024 )
            except socket.timeout:
                state = STATE_CLIENT_RUNNING
                continue
            except OSError:
                state = STATE_CLIENT_EXITING
                continue

            if not server_msg:
                print( '[client %s] server disconnected' % ( client_id ))
                state = STATE_CLIENT_EXITING
                continue

            decoded_msg = server_msg.decode()
            print( '[client %s] received message: %s' % ( client_id, decoded_msg ))
            msg_tokens = decoded_msg.split()

            if ( decoded_msg.startswith( 'Forwarding ' + MSG_SENT + ' from ' ) and len( msg_tokens ) >= 4 ):
                sender_id = msg_tokens[3]
                received_payload = ' '.join( msg_tokens[4:] )
                print( '[client %s] forwarded message payload: %s' % ( client_id, received_payload ))
                reply_msg = MSG_RECEIVED + ' from ' + client_id + ' to ' + sender_id
                cs.sendall( (reply_msg + '\n').encode() )
                print( '[client %s] sent message: %s' % ( client_id, reply_msg ))
            elif ( decoded_msg.startswith( 'Forwarding ' + MSG_RECEIVED + ' from ' ) and len( msg_tokens ) >= 4 ):
                sender_id = msg_tokens[3]
                print( '[client %s] interaction complete: received confirmation from %s' % ( client_id, sender_id ) + '. Ready for next message' )
                # clear pending message so user can type a new one
                has_received_confirmation = True
                pending_message = None
                message_text = ''
                has_sent_colour = False
                has_received_confirmation = False

            state = STATE_CLIENT_RUNNING
            
        elif ( state == STATE_CLIENT_EXITING ):
            break;

# all done!
state = STATE_CLIENT_EXITING
print( '[client %s] goodbye' % ( client_id ))
