import socket
import threading
import time
import hashlib
import random
import sys

# m is from m-bit Node id
m = 3

# Database is used to store the key value pairs at each node
class Database:
    def __init__(self):
        self.data = {}
    def insert(self, key, value):
        self.data[key] = value
    def delete(self, key):
        del self.data[key]
    def search(self, search_key):        
        if search_key in self.data:
            return self.data[search_key]
        else:
            print(self.data)
            return None

# NodeInfo represents the actual Node, it stores ip and port of a node       
class NodeInfo:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
    def __str__(self):
        return self.ip + "|" + str(self.port) 
 
# Node is used to manage the each node in the ring 
class Node:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = int(port)
        self.nodeinfo = NodeInfo(ip, port)
        self.id = self.hash(str(self.nodeinfo))
        self.predecessor = None
        self.successor = None
        self.finger_table = FingerTable(self.id)
        self.data_store = Database()
        self.request_handler = RequestHandler()
    
    def hash(self, message):
        digest = hashlib.sha1(message.encode()).hexdigest()
        digest = int(digest, 16) % pow(2,m)
        return digest

    def process_requests(self, message):
        operation = message.split("|")[0]
        args = []
        if( len(message.split("|")) > 1):
            args = message.split("|")[1:]
        result = "Done"
        if operation == 'insert_server':
            data = message.split('|')[1].split(":") 
            key = data[0]
            value = data[1]
            self.data_store.insert(key, value)
            result = 'Inserted'

        if operation == "delete_server":
            data = message.split('|')[1]
            self.data_store.data.pop(data)
            result = 'Deleted'

        if operation == "search_server":
            data = message.split('|')[1]
            if data in self.data_store.data:
                return self.data_store.data[data]
            else:
                return "NOT FOUND"
            
        if operation == "send_keys":
            id_of_joining_node = int(args[0])
            result = self.send_keys(id_of_joining_node)

        if operation == "insert":
            data = message.split('|')[1].split(":") 
            key = data[0]
            value = data[1]
            result = self.insert_key(key,value)

        if operation == "delete":
            data = message.split('|')[1]
            result = self.delete_key(data)

        if operation == 'search':
            data = message.split('|')[1]
            result = self.search_key(data)
                
        if operation == "join_request":
            result  = self.join_request_from_other_node(int(args[0]))

        if operation == "find_predecessor":
            result = self.find_predecessor(int(args[0]))

        if operation == "find_successor":
            result = self.find_successor(int(args[0]))

        if operation == "get_successor":
            result = self.get_successor()

        if operation == "get_predecessor":
            result = self.get_predecessor()

        if operation == "get_id":
            result = self.get_id()

        if operation == "notify":
            self.notify(int(args[0]),args[1],args[2])
    
        return str(result)

    def serve_requests(self, conn, addr):
        with conn:            
            data = conn.recv(1024)
            data = str(data.decode('utf-8'))
            data = data.strip('\n')
            data = self.process_requests(data)
            data = bytes(str(data), 'utf-8')
            conn.sendall(data)
    
    def start(self):
        thread_for_stabalize = threading.Thread(target = self.stabilize)
        thread_for_stabalize.start()
        thread_for_fix_finger = threading.Thread(target=  self.fix_fingers)
        thread_for_fix_finger.start()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.nodeinfo.ip, self.nodeinfo.port))
            s.listen()
            while True:
                conn, addr = s.accept()
                t = threading.Thread(target=self.serve_requests, args=(conn,addr))
                t.start()   

    def insert_key(self,key,value):
        id_of_key = self.hash(str(key))
        succ = self.find_successor(id_of_key)
        ip,port = self.get_ip_port(succ)
        self.request_handler.send_message(ip,port,"insert_server|" + str(key) + ":" + str(value) )
        return "Inserted at node id " + str(Node(ip,port).id) + " key was " + str(key) + " key hash was " + str(id_of_key)  

    def delete_key(self,key):
        id_of_key = self.hash(str(key))
        succ = self.find_successor(id_of_key)
        ip,port = self.get_ip_port(succ)
        self.request_handler.send_message(ip,port,"delete_server|" + str(key) )
        return "deleted at node id " + str(Node(ip,port).id) + " key was " + str(key) + " key hash was " + str(id_of_key)


    def search_key(self,key):
        id_of_key = self.hash(str(key))
        succ = self.find_successor(id_of_key)
        ip,port = self.get_ip_port(succ)
        data = self.request_handler.send_message(ip,port,"search_server|" + str(key) )
        return data


    def join_request_from_other_node(self, node_id):
        return self.find_successor(node_id)

    def join(self,node_ip, node_port):
        data = 'join_request|' + str(self.id)
        succ = self.request_handler.send_message(node_ip,node_port,data)
        ip,port = self.get_ip_port(succ)
        self.successor = Node(ip,port)
        self.finger_table.table[0][1] = self.successor
        self.predecessor = None
        
        if self.successor.id != self.id:
            data = self.request_handler.send_message(self.successor.ip , self.successor.port, "send_keys|"+str(self.id))
            for key_value in data.split(':'):
                if len(key_value) > 1:
                    self.data_store.data[key_value.split('|')[0]] = key_value.split('|')[1]

    def find_predecessor(self, search_id):
        if search_id == self.id:
            return str(self.nodeinfo)
        if self.predecessor is not None and  self.successor.id == self.id:
            return self.nodeinfo.__str__()
        if self.get_forward_distance(self.successor.id) > self.get_forward_distance(search_id):
            return self.nodeinfo.__str__()
        else:
            new_node_hop = self.closest_preceding_node(search_id)
            if new_node_hop is None:
                return "None"
            ip, port = self.get_ip_port(new_node_hop.nodeinfo.__str__())
            if ip == self.ip and port == self.port:
                return self.nodeinfo.__str__()
            data = self.request_handler.send_message(ip , port, "find_predecessor|"+str(search_id))
            return data

    def find_successor(self, search_id):
        if(search_id == self.id):
            return str(self.nodeinfo)
        predecessor = self.find_predecessor(search_id)
        if(predecessor == "None"):
            return "None"
        ip,port = self.get_ip_port(predecessor)
        data = self.request_handler.send_message(ip , port, "get_successor")
        return data

    def closest_preceding_node(self, search_id):
        closest_node = None
        min_distance = pow(2,m)+1
        for i in list(reversed(range(m))):
            if  self.finger_table.table[i][1] is not None and self.get_forward_distance_2nodes(self.finger_table.table[i][1].id,search_id) < min_distance  :
                closest_node = self.finger_table.table[i][1]
                min_distance = self.get_forward_distance_2nodes(self.finger_table.table[i][1].id,search_id)

        return closest_node

    def send_keys(self, id_of_joining_node):
        data = ""
        keys_to_be_removed = []
        for keys in self.data_store.data:
            key_id = self.hash(str(keys))
            if self.get_forward_distance_2nodes(key_id , id_of_joining_node) < self.get_forward_distance_2nodes(key_id,self.id):
                data += str(keys) + "|" + str(self.data_store.data[keys]) + ":"
                keys_to_be_removed.append(keys)
        for keys in keys_to_be_removed:
            self.data_store.data.pop(keys)
        return data

    
    def stabilize(self):
        while True:
            if self.successor is None:
                time.sleep(10)
                continue
            data = "get_predecessor"

            if self.successor.ip == self.ip  and self.successor.port == self.port:
                time.sleep(10)
            result = self.request_handler.send_message(self.successor.ip , self.successor.port , data)
            if result == "None" or len(result) == 0:
                self.request_handler.send_message(self.successor.ip , self.successor.port, "notify|"+ str(self.id) + "|" + self.nodeinfo.__str__())
                continue

            ip , port = self.get_ip_port(result)
            result = int(self.request_handler.send_message(ip,port,"get_id"))
            if self.get_backward_distance(result) > self.get_backward_distance(self.successor.id):
                self.successor = Node(ip,port)
                self.finger_table.table[0][1] = self.successor
            self.request_handler.send_message(self.successor.ip , self.successor.port, "notify|"+ str(self.id) + "|" + self.nodeinfo.__str__())
            print("===============================================")
            print("=============== NODE INFORMATION ==============")
            print(f"{'ID:':<20}{self.id}")
            if self.successor is not None:
                print(f"{'Successor ID:':<20}{self.successor.id}")
            if self.predecessor is not None:
                print(f"{'Predecessor ID:':<20}{self.predecessor.id}")
            print("===============================================")
            print("=============== FINGER TABLE ==================")
            print(f"{'Entry':<10}{'Interval Start':<15}{'Successor':<10}")
            for i, node in enumerate(self.finger_table.table):
                print(f"{i:<10}{node[0]:<15}{node[1].id if node[1] else 'None':<10}")
            print("===============================================")
            print("================= DATABASE ==================")
            print(str(self.data_store.data))
            print("+++++++++++++++ END +++++++++++++++++++++++++++")
            print()
            time.sleep(10)

    def notify(self, node_id , node_ip , node_port):
        if self.predecessor is not None:
            if self.get_backward_distance(node_id) < self.get_backward_distance(self.predecessor.id):
                self.predecessor = Node(node_ip,int(node_port))
                return
        if self.predecessor is None or self.predecessor == "None" or ( node_id > self.predecessor.id and node_id < self.id ) or ( self.id == self.predecessor.id and node_id != self.id) :
            self.predecessor = Node(node_ip,int(node_port))
            if self.id == self.successor.id:
                self.successor = Node(node_ip,int(node_port))
                self.finger_table.table[0][1] = self.successor
        
    def fix_fingers(self):
        while True:
            random_index = random.randint(1,m-1)
            finger = self.finger_table.table[random_index][0]
            data = self.find_successor(finger)
            if data == "None":
                time.sleep(10)
                continue
            ip,port = self.get_ip_port(data)
            self.finger_table.table[random_index][1] = Node(ip,port) 
            time.sleep(10)
    def get_successor(self):
        if self.successor is None:
            return "None"
        return self.successor.nodeinfo.__str__()

    def get_predecessor(self):
        if self.predecessor is None:
            return "None"
        return self.predecessor.nodeinfo.__str__()

    def get_id(self):
        return str(self.id)

    def get_ip_port(self, string_format):
        return string_format.strip().split('|')[0] , int(string_format.strip().split('|')[1])
    
    def get_backward_distance(self, node1):        
        disjance = 0
        if(self.id > node1):
            disjance =   self.id - node1
        elif self.id == node1:
            disjance = 0
        else:
            disjance=  pow(2,m) - abs(self.id - node1)
        return disjance

    def get_backward_distance_2nodes(self, node2, node1):        
        disjance = 0
        if(node2 > node1):
            disjance =   node2 - node1
        elif node2 == node1:
            disjance = 0
        else:
            disjance=  pow(2,m) - abs(node2 - node1)
        return disjance

    def get_forward_distance(self,nodeid):
        return pow(2,m) - self.get_backward_distance(nodeid)

    def get_forward_distance_2nodes(self,node2,node1):
        return pow(2,m) - self.get_backward_distance_2nodes(node2,node1)

# FingerTable is responsible for managing the finger table of each node.
class FingerTable:
    def __init__(self, my_id):
        self.table = []
        for i in range(m):
            x = pow(2, i)
            entry = (my_id + x) % pow(2,m)
            node = None
            self.table.append( [entry, node] )
        
    def print(self):
        for index, entry in enumerate(self.table):
            if entry[1] is None:
                print('Entry: ', index, " Interval start: ", entry[0]," Successor: ", "None")
            else:
                print('Entry: ', index, " Interval start: ", entry[0]," Successor: ", entry[1].id)


# RequestHandler is used to manage all the requests for sending messages from one node to another 
class RequestHandler:
    def __init__(self):
        pass
    def send_message(self, ip, port, message):
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM) 
  
        # connect to server on local computer 
        s.connect((ip,port)) 
        s.send(message.encode('utf-8')) 
        data = s.recv(1024) 
        s.close()
        return data.decode("utf-8") 
        

ip = "127.0.0.1"

# This if statement is used to check if the node joining is the first node of the ring or not
if len(sys.argv) == 3:
    print("JOINING RING")
    node = Node(ip, int(sys.argv[1]))

    node.join(ip,int(sys.argv[2]))
    node.start()

if len(sys.argv) == 2:
    print("CREATING RING")
    node = Node(ip, int(sys.argv[1]))
    node.predecessor = Node(ip,node.port)
    node.successor = Node(ip,node.port)
    node.finger_table.table[0][1] = node
    node.start()
