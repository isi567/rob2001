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


# define the IP address of the machine on which the server is running--where you want this client to connect.
# this could be a dotted quad address or 'localhost' (shorthand for the local machine).
HOST = 'localhost'   # or, e.g. '10.5.24.62'

# define the port for connecting to server.
# the value needs to match what the server used when it was initialised.
PORT = 50007

# define messages
MSG_REGISTER = 'REGISTER'
MSG_COLOUR = 'COLOUR'
MSG_COLOUR_RECEIVED = 'COLOUR_RECEIVED'
MSG_LIST = 'LIST'
MSG_ERROR = 'ERROR'

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_SEND_COLOUR    = 4
STATE_CLIENT_RECEIVE_COLOUR = 5




# client ID is command line argument
if ( len( sys.argv ) < 2 ):
    print( 'usage: python roboclient1.py <ID> [TARGET_ID]' )
    sys.exit( 1 )

client_id = sys.argv[1]
target_client = None
if ( len( sys.argv ) >= 3 ):
    target_client = sys.argv[2]

# shared run flag used by sender/receiver loops
running = True

# try to create and open a new socket object (called "cs", for client socket).
with socket.socket( socket.AF_INET, socket.SOCK_STREAM ) as cs:
    state = STATE_CLIENT_STARTING
    print( '[client %s] socket created' % ( client_id ))
    # bind the newly created socket object to the server's host and port (defined by the server).
    cs.connect(( HOST, PORT ))
    print( '[client %s] socket connected to host [%s], port [%s]' % ( client_id, HOST, PORT ))
    
    # send REGISTER <NAME>
    client_msg = MSG_REGISTER + ' ' + client_id
    print( '[client %s] sending message: %s' % ( client_id, client_msg ))
    cs.sendall( client_msg.encode() )
    print( '[client %s] sent message: %s' % ( client_id, client_msg ))

    # receive LIST SERVER <LIST>
    server_msg = cs.recv( 1024 )
    server_msg_text = server_msg.decode()
    print( '[client %s] received message: %s' % ( client_id, server_msg_text ))
    server_msg_tokens = server_msg_text.split()

    connected_clients_list = []

    if ( len( server_msg_tokens ) >= 2 and server_msg_tokens[0] == MSG_LIST and server_msg_tokens[1] == 'SERVER' ):
        connected_clients_list = server_msg_tokens[2:]
        print( '[client %s] connected clients: %s' % ( client_id, connected_clients_list ))
        # if no target provided on the command line, pick any client that is not self
        if ( not target_client ):
            for c in connected_clients_list:
                if ( c != client_id ):
                    target_client = c
                    break
        if ( target_client ):
            print( '[client %s] target client: %s' % ( client_id, target_client ))
        else:
            print( '[client %s] no target client available yet' % ( client_id ))
        state = STATE_CLIENT_RUNNING
    else:
        state = STATE_CLIENT_ERROR
        print( '[client %s] unexpected register response from server: %s' % ( client_id, server_msg_text ))

    def receive_messages():
        global running
        while( running ):
            server_msg = cs.recv( 1024 )
            if ( not server_msg ):
                print( '[client %s] server disconnected' % ( client_id ))
                running = False
                break

            server_msg_text = server_msg.decode()
            print( '[client %s] received message: %s' % ( client_id, server_msg_text ))
            server_msg_tokens = server_msg_text.split()

            if ( len( server_msg_tokens ) >= 3 and server_msg_tokens[0] in [ MSG_COLOUR, MSG_COLOUR_RECEIVED ] ):
                msg_type = server_msg_tokens[0]
                msg_from = server_msg_tokens[1]
                msg_to = server_msg_tokens[2]
                msg_colour = ' '.join( server_msg_tokens[3:] )

                if ( msg_type == MSG_COLOUR and msg_to == client_id ):
                    print( '[client %s] received colour from %s: %s' % ( client_id, msg_from, msg_colour ))
                    ack_msg = MSG_COLOUR_RECEIVED + ' ' + client_id + ' ' + msg_from
                    cs.sendall( ack_msg.encode() )
                    print( '[client %s] sent message: %s' % ( client_id, ack_msg ))
                elif ( msg_type == MSG_COLOUR_RECEIVED and msg_to == client_id ):
                    print( '[client %s] colour received confirmation from %s' % ( client_id, msg_from ))
                else:
                    print( '[client %s] ignoring message not addressed to me: %s' % ( client_id, server_msg_text ))
            elif ( len( server_msg_tokens ) >= 3 and server_msg_tokens[0] == MSG_ERROR ):
                print( '[client %s] server error: %s' % ( client_id, ' '.join( server_msg_tokens[2:] ) ))
            else:
                print( '[client %s] unexpected message format: %s' % ( client_id, server_msg_text ))

    if ( state == STATE_CLIENT_RUNNING ):
        receiver = threading.Thread( target=receive_messages, daemon=True )
        receiver.start()

        # send colours entered by the user to the target client via server
        while( running ):
            if ( not target_client ):
                print( '[client %s] no target client set, waiting...' % ( client_id ))
                time.sleep( 2 )
                continue

            colour = input( '[client %s] colour for %s (type quit to stop): ' % ( client_id, target_client ) ).strip()
            if ( not colour ):
                continue
            if ( colour.lower() == 'quit' ):
                running = False
                state = STATE_CLIENT_EXITING
                break

            state = STATE_CLIENT_SEND_COLOUR
            client_msg = MSG_COLOUR + ' ' + client_id + ' ' + target_client + ' ' + colour
            cs.sendall( client_msg.encode() )
            print( '[client %s] sent message: %s' % ( client_id, client_msg ))
            state = STATE_CLIENT_RUNNING

    if ( state == STATE_CLIENT_ERROR ):
        print( '[client %s] exiting in error state' % ( client_id ))

    state = STATE_CLIENT_EXITING

# all done!
state = STATE_CLIENT_EXITING
print( '[client %s] goodbye' % ( client_id ))
