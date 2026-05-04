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
MSG_SERVER = 'SERVER'
MSG_COLOUR = 'GREEN'

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_SEND_COLOUR    = 4
STATE_CLIENT_RECEIVE_COLOUR = 5

# client ID is command line argument
client_id = sys.argv[1]

# try to create and open a new socket object (called "cs", for client socket).
with socket.socket( socket.AF_INET, socket.SOCK_STREAM ) as cs:
    state = STATE_CLIENT_STARTING
    print( '[client %s] socket created' % ( client_id ))
    # bind the newly created socket object to the server's host and port (defined by the server).
    cs.connect(( HOST, PORT ))
    print( '[client %s] socket connected to host [%s], port [%s]' % ( client_id, HOST, PORT ))
    #state = STATE_CLIENT_RUNNING
    client_msg = MSG_REGISTER + ' ' + client_id
    print( '[client %s] sending message: %s' % ( client_id, client_msg ))
    cs.sendall( client_msg.encode() ) # send formatted message to server
    print( '[client %s] sent message: %s' % ( client_id, client_msg ))
    state = STATE_CLIENT_RUNNING
    while( True ):
        if ( state == STATE_CLIENT_RUNNING ):
            print( '[client %s] running' % ( client_id ))
            time.sleep( 5 )
            state = STATE_CLIENT_SEND_COLOUR
        elif ( state == STATE_CLIENT_SEND_COLOUR ): # check if server is alive
            client_msg = MSG_COLOUR + ' from ' + client_id + ' to ' + MSG_SERVER
            cs.sendall( client_msg.encode() ) # send formatted message to server
            print( '[client %s] sent message: %s' % ( client_id, client_msg ))
            state = STATE_CLIENT_RECEIVE_COLOUR
        elif ( state == STATE_CLIENT_RECEIVE_COLOUR ): # wait for message from server
            server_msg = cs.recv( 1024 )
            print( '[client %s] received message: %s' % ( client_id, server_msg.decode() ))
            if ( server_msg.decode() == 'Server has received ' + MSG_COLOUR + ' from ' + client_id): # server is alive
                state = STATE_CLIENT_RUNNING
            else:
                state = STATE_CLIENT_ERROR
                print( '[client %s] unexpected message received from server: %s' % ( client_id, server_msg.decode() ))
        elif ( state == STATE_CLIENT_ERROR ):
            state = STATE_CLIENT_EXITING
            print( '[client %s] exiting in error state' % ( client_id ))
        elif ( state == STATE_CLIENT_EXITING ):
            break;

# all done!
state = STATE_CLIENT_EXITING
print( '[client %s] goodbye' % ( client_id ))
