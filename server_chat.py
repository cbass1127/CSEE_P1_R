import sys
import util
import os
import socket
import signal
import datetime
import time
import threading

accept_msg = 'Client table updated.'
client_ips = dict()
client_ips_map = dict()
client_map = dict()
listening = False
name_set = set()
server_sock = None
ACK_SC = 0
KILL = False



def timeout_handler(signum, frame):
    raise util.TimoutException('timout!')

def send_ACK(socket, addr):
    '''
    Sends specially formatted ACK w/ MAGIC_NUM
    :return: None
    '''
    util.Send(socket, str(util.MAGIC_NUM).encode(), addr)

def send_ERR(socket, addr):
    '''
    Sends specially formatted ERR msg w/ MAGIC_NUM
    :return: None
    '''
    s = str(util.MAGIC_NUM) + 'E'
    send_s = s.encode()
    util.Send(socket, send_s, addr)

def server_setup():
    '''
    Performs inital server setup. Binds to port.
    :return: working server socket
    '''
    port = util.Port(sys.argv[1])
    server_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    try:
        server_sock.bind(('0.0.0.0', port))
    except:
        util.Die('cannot bind to port {0}'.format(port))
    util.pmessage('', False)
    return server_sock

def broadcast_update(socket, u_address, u_port, u_name, u_online_status):
    '''
    Broadcasts table update to all registered clients
    :return: None
    '''
    s = 'TU ' + u_address + ' ' + str(u_port) + ' ' + u_name + ' ' + str(int(u_online_status))
    send_s = str.encode(s)
    for dest in client_map.keys():
        util.Send(socket,send_s,dest)

def broadcast_message(socket, sender_name, message):
    '''
    Sends Channel Message to all clients. If a client does not respond with ACK after 0.5s, they are set to offline
    and the message gets saved in their file.
    :return: None
    '''
    global listening
    global name_set
    global accept_msg
    for dest in client_map.keys():
        s = 'Channel_Message ' + sender_name + ': ' + message 
        sender_dest = (client_ips_map[sender_name][0], client_ips_map[sender_name][1])
        if sender_dest != dest:
            send_s = s.encode()
            util.Send(socket, send_s, dest)
    listen_thread = threading.Thread(target = server_listen, args = (server_sock, True)) #start a concurrent lisening thread to wait on ACKs 
    listening = True
    name_set = set(client_ips_map.keys()) # set global name_set to be full list of clients
    name_set.remove(sender_name) # remove sender from list of clients
    listen_thread.start() #start ACK-waiting thread
    time.sleep(0.5)
    listening = False
    s = 'Channel_Message ' + sender_name + ': ' + str(datetime.datetime.now()) + ' ' +  message 
    for name in name_set:
        p = name
        if os.path.exists(p):
            f = open(p, 'a')
        else:
            f = open(p, 'w')
        f.write(s + '\n')
        f.close()
        if client_ips_map[name][2]: 
            addr = client_ips_map[name][0]
            port = client_ips_map[name][1]
            client_ips_map[name] = (addr, port, False)
            client_map[(addr, port)] = (name , False)
            broadcast_update(server_sock, addr, port, name, False)

    listen_thread.join()


def send_table(socket, dest):
    '''
    Send the entire table to a client. TUW and TUF prefixes are for bookkeeping at client side.
    :return: None
    '''
    count = len(client_map.keys()) - 1
    if count == -1:
        return
    k = None
    for client in client_map.keys():
        if count == 0:
            k = client
            break;
        count-=1
        s = 'TUW ' + client[0] + ' ' + str(client[1]) + ' ' + client_map[client][0] + ' ' + str(int(client_map[client][1]))
        send_s = str.encode(s)
        util.Send(socket,send_s,dest)
    s = 'TUF ' + k[0] + ' ' + str(k[1]) + ' ' + client_map[k][0] + ' ' + str(int(client_map[k][1]))
    send_s = str.encode(s)
    util.Send(socket,send_s,dest)

def send_mail(sock, name, addr):
    '''
    Opens file associated with name and sends the entire contents to client.
    :return: None
    '''
    s = 'MAIL '
    clnt_addr = client_ips_map[name][0]
    clnt_port = client_ips_map[name][1]
    if not os.path.exists(name):
        return
    with open(name) as f:
        for line in f:
            s+= (line + '\n')
    send_s = s.encode()
    util.Send(sock, send_s, (clnt_addr, clnt_port))
    os.remove(name)

def add_client(address, port, name, online_status):
    '''
    Adds a client to global maps of clients for first time.
    :return: None
    '''
    client_ips[address] = 1
    client_map[(address, port)] = (name , online_status)
    client_ips_map[name] = (address,port, online_status)
        
#def serve_client(socket):
#    while(True):
#        message, addrp = socket.recvfrom(util.SIZE)
#        process_req(message, addrp[0], addrp[1])
#    sys.exit()
#
def wait_online_ACK(sock, local_SC):
    '''
    Waits for ACK when server is checking if client is online.
    :return: None
    '''
    global ACK_SC
    time.sleep(0.3)
    if ACK_SC != local_SC:
        return True
    return False

def clnt_online(sock, addr):
    '''
    Sends message to client at addr to see if they are online.
    :return: None
    '''
    global ACK_SC
    s = str(util.MAGIC_NUM)+'O'
    send_s = s.encode()
    util.Send(sock, send_s, addr)
    local_SC = ACK_SC
    return wait_online_ACK(sock, local_SC)


def server_listen(server_sock, ACK = False):
    '''
    Main loop of server. Listens for incoming requests for sendsave messages, dereg/reg requests, and broadcast messages
    :return: None
    '''
    global listening
    global name_set
    global ACK_SC
    condition = listening if ACK else True
    while(True): 
        sender_message, sender_address = server_sock.recvfrom(util.SIZE)
        sender_message = sender_message.decode('UTF-8')
        if sender_address not in client_map.keys():
            if sender_message in client_ips_map.keys():
                util.Send(server_sock, 'nick name already exists!'.encode(), (sender_address[0], sender_address[1]))
            else:
                online_status = True
                send_table(server_sock, sender_address)
                add_client(sender_address[0], sender_address[1], sender_message, online_status)
                broadcast_update(server_sock, sender_address[0], sender_address[1], sender_message, online_status)
                util.Send(server_sock, 'Welcome, You are registered.'.encode(), (sender_address[0], sender_address[1]))
        split_message = sender_message.split()
        if(len(split_message) == 2 and split_message[0] == 'dereg' and split_message[1] in client_ips_map.keys()): #dereg request
            name = split_message[1]
            if name not in client_ips_map.keys():
                return
            clnt_addr = client_ips_map[name][0]
            clnt_port = client_ips_map[name][1] 
            client_map[(clnt_addr, clnt_port)] = (name, False)
            client_ips_map[name] = (clnt_addr, clnt_port, False)
            send_ACK(server_sock, sender_address)
            broadcast_update(server_sock, client_ips_map[name][0], client_ips_map[name][1], name, False)
        elif(len(split_message) >= 3 and split_message[0] == 'sendsave' and split_message[1] in client_ips_map.keys()): #sendsave message. If client isnt online, save msg to thier file.
            name = split_message[1]
            sender_name = client_map[sender_address][0]
            clnt_addr = client_ips_map[name][0]
            clnt_port = client_ips_map[name][1]  
            isonline = clnt_online(server_sock, (clnt_addr, clnt_port))
            if not client_ips_map[name][2] or not isonline:
                send_ACK(server_sock, sender_address)
                p =  name
                if os.path.exists(p):
                    f = open(p, 'a')
                else:
                    f = open(p, 'w')
                f.write(sender_name + ': ' + str(datetime.datetime.now()) + ' ' + ' '.join(split_message[2:]) + '\n')
                f.close()
                if not isonline and client_ips_map[name][2] != isonline:
                    client_ips_map[name] = (clnt_addr, clnt_port, False)
                    client_map[(clnt_addr, clnt_port)] = (name , False)
            else:
                send_ERR(server_sock, sender_address)
                broadcast_update(server_sock, clnt_addr, clnt_port, name, True)
        elif(len(split_message) == 2 and split_message[0] == str(util.MAGIC_NUM) + 'R'): #request to register
            name = split_message[1]
            if name not in client_ips_map.keys():
                return
            clnt_addr = client_ips_map[name][0]
            clnt_port = client_ips_map[name][1]
            send_mail(server_sock, name, (clnt_addr, clnt_port))
            client_map[(clnt_addr, clnt_port)] = (name, True)
            client_ips_map[name] = (clnt_addr, clnt_port, True)
            broadcast_update(server_sock, clnt_addr, clnt_port, name, True)
            send_table(server_sock, (clnt_addr, clnt_port)) 
        elif len(split_message) >= 2 and split_message[0] == 'send_all': #broadcast message from client
            sender_name = client_map[sender_address][0]
            message = ' '.join(split_message[1:])
            send_ACK(server_sock, sender_address)
            broadcast_message(server_sock, sender_name, message)
        elif len(split_message) == 2 and split_message[0] == str(util.MAGIC_NUM):# ACK from specific client. Once recieved client can be removed from set
            name = split_message[1]                                              # of clients that ACK has not recvd from
            if name in name_set:
                name_set.remove(name)
        elif len(split_message) == 1 and split_message[0] == str(util.MAGIC_NUM): # regular ACK
            ACK_SC+=1

def main():
    '''
    Main function: performs server setup and starts listening
    '''
    global server_sock
    if len(sys.argv) != 2:
        util.Die('usage: {0} -s <port>'.format(util.MAIN_P))
    server_sock = server_setup()
    server_listen(server_sock) 
if __name__ == '__main__':
    main()
