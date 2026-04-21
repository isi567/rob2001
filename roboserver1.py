#--
# roboserver1.py
#
# Example multi-robot system server programme
# from: https://docs.python.org/3/library/socket.html
# with comments and debugging prints by esklar/11-feb-2025
# based on esklar/echoserver4.py (mar-2026)
#
# $ python roboserver1.py
#
#--

# import python socket-handling library.
import socket
import threading

# define the IP address of the machine on which the server is running.
# this could be a dotted quad address or 'localhost' (shorthand for the local machine).
HOST = 'localhost'   # or, e.g. '10.5.24.62'

# define the port for clients to connect to this socket.
# the value could be almost anything--that isn't already in use.
PORT = 50007

# define messages
MSG_REGISTER = 'REGISTER'
MSG_PING = 'PING'
MSG_PONG = 'PONG'

# define server state variables
STATE_SERVER_STARTING = 0
STATE_SERVER_EXITING  = 1
STATE_SERVER_RUNNING  = 2

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_RECEIVE_PING = 4
STATE_CLIENT_SEND_PONG    = 5



#--
# define thread for handling communication with a single client.
# more than one of these can be instantiated...
#--
class client_thread( threading.Thread ):
    # this function is called when a new thread object is instantiated
    def __init__( self, name, connection ):
        threading.Thread.__init__( self )
        self.name = name
        self.connection = connection
        self.state = STATE_CLIENT_STARTING

    # this function sets the object's state variable
    def setState( self, state0 ):
        self.state = state0

    # this function is called when the thread object starts
    def run( self ):
        self.setState( STATE_CLIENT_RUNNING )
        print( '[server client %s]: running' % ( self.name ))
        while True:
            print( '[server client %s]: waiting for message...' % ( self.name ))
            client_msg = self.connection.recv( 1024 ) # receive message from client
            print( '[server client %s]: message received: %s' % ( self.name, client_msg.decode() ))
            if not client_msg:
                # if an empty message is received, then the client has disconnected; so exit.
                self.setState( STATE_CLIENT_EXITING )
                break
            else:
                client_msg_tokens = client_msg.decode().split()
                if ( client_msg_tokens[0] == MSG_REGISTER ):
                    self.name = client_msg_tokens[1]
                elif ( client_msg_tokens[0] == MSG_PING ):
                    server_msg = MSG_PONG
                    print( '[server client %s]: sending message [%s]' % ( self.name, server_msg ))
                    self.connection.sendall( server_msg.encode() ) # send message to client
        self.setState( STATE_CLIENT_EXITING )
        print( '[server client %s]: exiting' % ( self.name ))



#--
# MAIN
#--

# define state variable
server_state = STATE_SERVER_STARTING

# keep track of clients
my_clients = []

# try to create and open a new socket object (called "ss", for server socket).
with socket.socket( socket.AF_INET, socket.SOCK_STREAM ) as ss:
    print( 'socket created' )
    # bind the newly created socket object to the specific host and port defined above.
    ss.bind(( HOST, PORT ))
    print( 'socket bound to host [%s], port [%s]' % ( HOST, PORT ))
    # now wait for requests to connect to the socket.
    ss.listen( 1 )
    print( 'listening for connections...' )
    server_state = STATE_SERVER_RUNNING
    while True:
        # accept any connection, saving a connection object and its address.
        connection, addr = ss.accept()
        print( '[server main] connected by robot client: ', addr )
        # now loop forever, reading messages on the socket and sending back acknowledgments.
        name = str( addr )
        print( '[server main] creating robot client thread named: [%s]' % ( name ))
        my_clients.append( client_thread( name, connection ))
        my_clients[-1].start()
        my_clients[-1].setState( STATE_CLIENT_RUNNING )

server_state = STATE_SERVER_EXITING
print( '[server main] exiting' )
