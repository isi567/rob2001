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

# change on mimi branch
# change on yasmin branch

# import python socket-handling library.
import socket
import threading

# define the IP address of the machine on which the server is running.
# this could be a dotted quad address or 'localhost' (shorthand for the local machine).
#HOST = 'localhost'   # or, e.g. '10.5.24.62'
HOST = '10.247.26.138'

# define the port for clients to connect to this socket.
# the value could be almost anything--that isn't already in use.
PORT = 50007

# define messages
MSG_REGISTER = 'REGISTER'
MSG_SENT = 'MESSAGE'
MSG_RECEIVED = 'MESSAGE_RECEIVED'

# define server state variables
STATE_SERVER_STARTING = 0
STATE_SERVER_EXITING  = 1
STATE_SERVER_RUNNING  = 2

# define client thread state variables
STATE_CLIENT_STARTING     = 0
STATE_CLIENT_EXITING      = 1
STATE_CLIENT_RUNNING      = 2
STATE_CLIENT_ERROR        = 3
STATE_CLIENT_RECEIVE_SENT = 4
STATE_CLIENT_SEND_SENT    = 5

ClientList = []
ClientListLock = threading.Lock()

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
        buffer = ''
        while True:
            print( '[server client %s]: waiting for message...' % ( self.name ))
            try:
                chunk = self.connection.recv( 1024 ) # receive message from client
            except:
                chunk = b''
            if not chunk:
                # if an empty message is received, then the client has disconnected; so exit.
                self.setState( STATE_CLIENT_EXITING )
                break

            buffer += chunk.decode()
            lines = buffer.split( '\n' )
            buffer = lines[-1]  # keep incomplete line in buffer
            
            for line in lines[:-1]:
                if not line.strip():
                    continue
                decoded_msg = line.strip()
                print( '[server client %s]: message received: %s' % ( self.name, decoded_msg ))
                client_msg_tokens = decoded_msg.split()
                if ( client_msg_tokens[0] == MSG_REGISTER ):
                    self.name = client_msg_tokens[1]
                elif ( client_msg_tokens[0] == MSG_SENT or client_msg_tokens[0] == MSG_RECEIVED ):
                    msg_type = client_msg_tokens[0]
                    msg_payload = ' '.join( client_msg_tokens[3:] )
                    server_msg = 'Server has received ' + msg_type + ' from ' + self.name
                    print( '[server client %s]: sending message [%s]' % ( self.name, server_msg ))
                    self.connection.sendall( (server_msg + '\n').encode() ) # send message to client
                    forwarded_msg = 'Forwarding ' + msg_type + ' from ' + self.name
                    if ( msg_payload ):
                        forwarded_msg += ' ' + msg_payload
                    forwarded = False
                    with ClientListLock:
                        for other_client in ClientList:
                            if other_client is not self and other_client.state == STATE_CLIENT_RUNNING:
                                print( '[server client %s]: forwarding message [%s] to [%s]' % ( self.name, forwarded_msg, other_client.name ))
                                other_client.connection.sendall( (forwarded_msg + '\n').encode() )
                                forwarded = True
                                break
                    if not forwarded:
                        print( '[server client %s]: no second client available for forwarding' % ( self.name ))


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
        new_client = client_thread( name, connection )
        with ClientListLock:
            ClientList.append( new_client )
        new_client.start()
        new_client.setState( STATE_CLIENT_RUNNING )

server_state = STATE_SERVER_EXITING
print( '[server main] exiting' )
