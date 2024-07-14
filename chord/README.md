## Chord

---

This is a simple implementation of CHORD Peer to Peer protocol

This project has two components, Peer (`node.py`) and Client(`client.py`).

## USAGE

---

### Peer:

_Usage:_

1. To create the first node joining the ring
   `python node.py <port_number>`
   (port_number is the port at which the node will be running).

2. To create node to join existing ring.
   `python node.py <port number of new node> <port number of existing node>`
   (port number of new node is the port at which the node will be running and port number of existing node is the port number of any of the other existing nodes in the ring).

### Client:

_Usage:_ `python client.py`

1. Client program first asks us to enter a port number for any existing node in the ring.

2. Then, Client program will provide us a set of options:
   1. Enter Data
   2. Get Data
   3. Delete Data
   4. Exit
