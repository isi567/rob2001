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


# define the IP address of the machine on which the server is running--where you want this client to connect.
# this could be a dotted quad address or 'localhost' (shorthand for the local machine).
HOST = 'localhost'   # or, e.g. '10.5.24.62'

# define the port for connecting to server.
# the value needs to match what the server used when it was initialised.
PORT = 50007

# define messages
MSG_REGISTER = 'REGISTER'
MSG_PING = 'PING'
MSG_PONG = 'PONG'

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_SEND_PING    = 4
STATE_CLIENT_RECEIVE_PONG = 5




# client ID is command line argument
client_id = sys.argv[1]

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

    # receive PONG SERVER <LIST>
    server_msg = cs.recv( 1024 )
    server_msg_text = server_msg.decode()
    print( '[client %s] received message: %s' % ( client_id, server_msg_text ))
    server_msg_tokens = server_msg_text.split()
    
    connected_clients_list = []

    if ( len( server_msg_tokens ) >= 3 and server_msg_tokens[0] == MSG_PONG and server_msg_tokens[1] == 'SERVER' ):
        connected_clients_list = server_msg_tokens[2:]
        print( '[client %s] connected clients: %s' % ( client_id, connected_clients_list ))
        state = STATE_CLIENT_RUNNING
    else:
        state = STATE_CLIENT_ERROR
        print( '[client %s] unexpected register response from server: %s' % ( client_id, server_msg_text ))

    while( True ):
        if ( state == STATE_CLIENT_RUNNING ):
            print( '[client %s] running - waiting for messages...' % ( client_id ))
            # switch to receive state to wait for incoming messages
            state = STATE_CLIENT_RECEIVE_PONG
        elif ( state == STATE_CLIENT_RECEIVE_PONG ): # wait for message from other client
            try:
                cs.settimeout( 30 )
                server_msg = cs.recv( 1024 )
            except socket.timeout:
                print( '[client %s] socket timeout - still waiting' % ( client_id ))
                state = STATE_CLIENT_RECEIVE_PONG
                continue

            if not server_msg:
                print( '[client %s] connection closed by server' % ( client_id ))
                state = STATE_CLIENT_EXITING
                continue

            server_msg_text = server_msg.decode()
            print( '[client %s] received message: %s' % ( client_id, server_msg_text ))
            server_msg_tokens = server_msg_text.split()

            if ( len( server_msg_tokens ) >= 3 ):
                msg_type = server_msg_tokens[0]
                msg_from = server_msg_tokens[1]
                msg_to = server_msg_tokens[2]

                if ( msg_type == MSG_PING and msg_to == client_id ):
                    # received PING from another client
                    print( '[client %s] received PING from %s' % ( client_id, msg_from ))
                    time.sleep( 5 )
                    response_msg = MSG_PONG + ' ' + client_id + ' ' + msg_from
                    cs.sendall( response_msg.encode() )
                    print( '[client %s] sent message: %s' % ( client_id, response_msg ))
                    state = STATE_CLIENT_RECEIVE_PONG
                elif ( msg_type == MSG_PONG and msg_to == client_id ):
                    # received PONG from another client
                    print( '[client %s] received PONG from %s' % ( client_id, msg_from ))
                    time.sleep( 5 )
                    response_msg = MSG_PING + ' ' + client_id + ' ' + msg_from
                    cs.sendall( response_msg.encode() )
                    print( '[client %s] sent message: %s' % ( client_id, response_msg ))
                    state = STATE_CLIENT_RECEIVE_PONG
                else:
                    state = STATE_CLIENT_ERROR
                    print( '[client %s] unexpected message: %s' % ( client_id, server_msg_text ))
            else:
                state = STATE_CLIENT_ERROR
                print( '[client %s] unexpected message format: %s' % ( client_id, server_msg_text ))
        elif ( state == STATE_CLIENT_ERROR ):
            state = STATE_CLIENT_EXITING
            print( '[client %s] exiting in error state' % ( client_id ))
        elif ( state == STATE_CLIENT_EXITING ):
            break;

# all done!
state = STATE_CLIENT_EXITING
print( '[client %s] goodbye' % ( client_id ))
