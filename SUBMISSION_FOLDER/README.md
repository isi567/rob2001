# rob2001
Assignment 2

RobocolorServer2
- The file containing our server, which allows communication between clients
- The server transfers messages from one client to another client through network ports
- It is run by typing 'python robocolorServer2.py' into the terminal

Human-Robot Client
- The human-robot client can be run as both waiter and chef robots
- It defines network protocols and triolobot functions (colour detection, movement and underlights)
- The human-Robot client, when acting as a chef can:
    - Register itself with the server
    - Recieve messages from waiter
    - Send messages to waiter

- The human-robot client, when acting as a waiter can:
    - Register iself with the server
    - Recieve human input (typed) messages
    - Communicate with the human via text output on its screen
    - Send messages to chef
    - Recieve messages from chef
    - Detect and identify colours
    - Move from resteraunt to kitchen and back (Red, Blue) to fetch sauce/the bill
    - Move from the kitchen to the garden and back (Green, Red) to fetch produce
    
Robot-Robot Client
- There are 2 clients, one for chef and one for waiter for the robot-robot system

- The chef client:
    - Registers itself with the server
    - choses a random message instruction from the list, to send to the waiter (e.g. cucumber) to begin the interaction
    - can recieve messages from the waiter
    - can send responses to the waiter
    (this loops until program is killed)

- The waiter client:
    - Defines trilobot functions (colour detection, movement and underlights)
    - Register iself with the server
    - Send messages to chef (e.g. found colour)
    - Recieve messages from chef (e.g. cucumber)
    - Detect and identify colours
    - Move from kitchen to garden and back to fetch produce and bring it to the kitchen
    
