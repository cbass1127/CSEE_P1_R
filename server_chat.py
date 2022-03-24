import sys
import util
import os
import socket
import signal
import datetime
import time

accept_msg = 'Client table updated.'
client_ips = dict()
client_ips_map = dict()
client_map = dict()



def timeout_handler(signum, frame):
    raise util.TimoutException('timout!')

def send_ACK(socket, addr):
    util.Send(socket, str(util.MAGIC_NUM).encode(), addr)

#def wait_ACK(send_addr, local_SC, client = True):
#    global ACK_recvd
#    global ACK_SC
#    name = ''
#    if client:
#        name = friend_ip_map[(send_addr[0], send_addr[1])][0]
#    time.sleep(0.5)
#    if(local_SC == ACK_SC):
#        if client:
#            friend_ip_map[(send_addr[0], send_addr[1])] = (name ,False)
#            util.pmessage(' No ACK from ' + name + ' ,message sent to server.')
#        return False
#    else:
#        if client:
#            util.pmessage('Message recieved by ' + name + '.')
#        return True
#
def send_ERR(socket, addr):
    s = str(util.MAGIC_NUM) + 'E'
    send_s = s.encode()
    util.Send(socket, send_s, addr)

def server_setup():
    port = util.Port(sys.argv[1])
    server_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    try:
        server_sock.bind(('0.0.0.0', port))
    except:
        util.Die('cannot bind to port {0}'.format(port))
    util.pmessage('', False)
    return server_sock

def broadcast_update(socket, u_address, u_port, u_name, u_online_status):
    s = 'TU ' + u_address + ' ' + str(u_port) + ' ' + u_name + ' ' + str(int(u_online_status))
    send_s = str.encode(s)
    for dest in client_map.keys():
        util.Send(socket,send_s,dest)

def broadcast_message(socket, sender_name, message):
    for dest in client_map.keys():
        s = 'Channel_Message ' + sender_name + ': ' + message 
        sender_dest = (client_ips_map[sender_name][0], client_ips_map[sender_name][1])
        if sender_dest != dest:
            if client_ips_map[sender_name][2]:
                send_s = s.encode()
                util.Send(socket, send_s, dest)
            else:
                    p = client_map[dest][0]
                    if os.path.exists(p):
                        f = open(p, 'a')
                    else:
                        f = open(p, 'w')
                    f.write(s + '\n')
                    f.close()
    
def send_table(socket, dest):
    for client in client_map.keys():
        s = 'TU ' + client[0] + ' ' + str(client[1]) + ' ' + client_map[client][0] + ' ' + str(int(client_map[client][1]))
        send_s = str.encode(s)
        util.Send(socket,send_s,dest)

def send_mail(sock, name, addr):
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
    client_ips[address] = 1
    client_map[(address, port)] = (name , online_status)
    client_ips_map[name] = (address,port, online_status)
    util.pmessage(accept_msg)
        
def process_req(message, address, port):
    print('Recieved! ', message.decode())


def serve_client(socket):
    while(True):
        message, addrp = socket.recvfrom(util.SIZE)
        process_req(message, addrp[0], addrp[1])
    sys.exit()

def wait_online_ACK(sock):
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.5)
        sender_message, sender_address = sock.recvfrom(util.SIZE)
        signal.setitimer(signal.ITIMER_REAL, 0)
        return True
    except util.TimoutException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        return False

def clnt_online(sock, addr):
    s = str(util.MAGIC_NUM)+'O'
    send_s = s.encode()
    util.Send(sock, send_s, addr)
    wait_online_ACK(sock)

def main():
    if len(sys.argv) != 2:
        util.Die('usage: {0} -s <port>'.format(util.MAIN_P))
    signal.signal(signal.SIGALRM, timeout_handler)
    server_sock = server_setup()
    while(True): 
        sender_message, sender_address = server_sock.recvfrom(util.SIZE)
        sender_message = sender_message.decode('UTF-8')
        if sender_address not in client_map.keys():
            online_status = True
            send_table(server_sock, sender_address)
            add_client(sender_address[0], sender_address[1], sender_message, online_status)
            broadcast_update(server_sock, sender_address[0], sender_address[1], sender_message, online_status)
        split_message = sender_message.split()
        if(len(split_message) == 2 and split_message[0] == 'dereg' and split_message[1] in client_ips_map.keys()):
            name = split_message[1]
            clnt_addr = client_ips_map[name][0]
            clnt_port = client_ips_map[name][1] 
            client_map[(clnt_addr, clnt_port)] = (name, False)
            client_ips_map[name] = (clnt_addr, clnt_port, False)
            send_ACK(server_sock, sender_address)
            broadcast_update(server_sock, client_ips_map[name][0], client_ips_map[name][1], name, False)
            util.pmessage(accept_msg)
        elif(len(split_message) == 3 and split_message[0] == 'sendsave' and split_message[1] in client_ips_map.keys()):
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
                f.write(sender_name + ': ' + str(datetime.datetime.now()) + ' ' + split_message[2] + '\n')
                f.close()
                if not isonline and client_ips_map[name][2] != isonline:
                    client_ips_map[name] = (clnt_addr, clnt_port, False)
                    client_map[(clnt_addr, clnt_port)] = (name , False)
                    broadcast_update(server_sock, clnt_addr, clnt_port, name, False)
                    util.pmessage(accept_msg)
            else:
                send_ERR(server_sock, sender_address)
                broadcast_update(server_sock, clnt_addr, clnt_port, name, True)
        elif(len(split_message) == 2 and split_message[0] == str(util.MAGIC_NUM) + 'R'):
            name = split_message[1]
            send_mail(server_sock, name, (clnt_addr, clnt_port))
            clnt_addr = client_ips_map[name][0]
            clnt_port = client_ips_map[name][1]
            client_map[(clnt_addr, clnt_port)] = (name, True)
            client_ips_map[name] = (clnt_addr, clnt_port, True)
            broadcast_update(server_sock, clnt_addr, clnt_port, name, True)
            util.pmessage(accept_msg)
        elif len(split_message) == 2 and split_message[0] == 'send_all':
            sender_name = client_map[sender_address][0]
            message = split_message[1]
            broadcast_message(server_sock, sender_name, message)
            send_ACK(server_sock, sender_address)
        
if __name__ == '__main__':
    main()
