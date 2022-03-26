import sys
import util
import os
import socket
import threading
import signal
import time


ACK_recvd = True
ERR_recvd = False
listening = True
ACK_SC = 0
client_ips = dict()
friend_map = dict()
friend_ip_map = dict()
lock = threading.Semaphore(1)
server_dest = ('0.0.0.0', 0)
my_name = ''
accept_msg = 'Client table updated.'

def send_ACK(socket, addr, use_name = False, name = ''):
    '''
    Sends specially formatted ACK. MAGIC_NUM is defined in util.py and is used for special
    communication between client and server.
    :return: None
    '''
    if not use_name:
        util.Send(socket, str(util.MAGIC_NUM).encode(), addr)
    else:
        s = str(util.MAGIC_NUM) + ' ' + name
        util.Send(socket, s.encode(), addr)

def timeout_handler(signum, frame):
    raise util.timoutexception('timout!')

def wait_ACK(send_addr, local_SC, client = True, duration = 0.5):
    '''
    Sleeps for duration seconds and checks if an ACK has bee recieved to the listening thread.
    :return: Boolean indicating whether an ACK was recieved.
    '''
    global ACK_recvd
    global ACK_SC
    name = ''
    if client:
        name = friend_ip_map[(send_addr[0], send_addr[1])][0]
    time.sleep(duration)
    if(local_SC == ACK_SC):
        if client:
            friend_ip_map[(send_addr[0], send_addr[1])] = (name ,False)
            util.pmessage(' No ACK from ' + name + ' ,message sent to server.')
        return False
    else:
        if client:
            util.pmessage('Message recieved by ' + name + '.')
        return True

def notify_leave(sock, name, addr):
    '''
    sends specially formatted message to server indicating that client wants to deregister.
    :return:None
    '''
    s = 'dereg ' + name
    util.Send(sock, s.encode(), addr)


def notify_server_leave(sock, name, send_addr, local_SC):
    '''
    tries to deregister 6 times (inital try + five retries). Has to wait for ack each time.
    :return: boolean indicating whether server ackd client's deregistration
    '''
    count = 0
    status = False
    while(count < 6 and (not status)):
        notify_leave(sock, name, send_addr)
        status = wait_ACK(send_addr, local_SC, False)
        count+=1
    return status

def notify_server_channel_msg(sock, message, send_addr, local_SC):
    '''
    tries to send channel message 6 times (inital try + five retries). Has to wait for ack each time.
    :return: boolean indicating whether server ACKd client's channel message
    '''
    count = 0
    status = False
    while(count < 6 and (not status)):
        util.Send(sock, message, send_addr)
        status = wait_ACK(send_addr, local_SC, False, 0.5)
        count+=1
    if status:
        util.pmessage('Message recieved by server')
    else:
        util.pmessage('Server not responding')
    return status

def wait_ACK_ERR(local_SC):
    '''
    Pertains to savemessages. Wait either for ACK of savemessage, error (indicating that client is actually online),
    or server not responding 
    :return: -1,0,1 indicating status of savemessage
    '''
    global ERR_recvd
    time.sleep(0.5)
    evalu = time.time()
    if(local_SC == ACK_SC and not ERR_recvd):
        return 0
    elif(local_SC != ACK_SC):
        return 1
    elif(ERR_recvd):
        return -1

def send_save_message(sock, name, message, local_SC):
    '''
    Attempts to send savemessage. Uses wait_ACK_err for status of savemessage.
    :return: None
    '''    
    global server_dest
    global ERR_recvd
    global lock
    global ACK_SC
    s = 'sendsave ' + name + ' ' + message
    lock.acquire()
    local_SC = ACK_SC
    ERR_recvd = False
    lock.release()
    time.sleep(0.5)
    util.Send(sock, s.encode(), server_dest)
    ret = wait_ACK_ERR(local_SC)
    if ret == 1:
        util.pmessage('Messages recieved by the server and saved')
    elif ret == -1:
        util.pmessage('Client ' + name + ' exists!!')
    else:
        util.pmessage('Sendsave message failed. Try again.')
def clnt_setup():
    '''
    Client setup. Binds client to specified port given via CLA.
    :return: working UDP socket for client
    '''
    my_port = util.Port(sys.argv[4]) 
    clnt_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); 
    try:
        clnt_sock.bind(('0.0.0.0', my_port))
    except:
        util.Die('Could Not bind to port '+ str(my_port))
    return clnt_sock


def reg_to_server(sock, name, addr):
    '''
    Uses MAGIC_NUM to register with server after deregistration
    :return: None
    '''
    s = str(util.MAGIC_NUM) + 'R' + ' ' + name
    send_s = s.encode()
    util.Send(sock, send_s, addr)

def display_mail(messages):
    '''
    Displays mail sent to offline client when they log back in via registering.
    :return: None
    '''
    util.pmessage('YOU HAVE MESSAGES')
    lines = messages.split('\n') 
    for line in lines:
        if line.strip() != '':
            util.pmessage(line + '\n', False)

def clnt_send_h(sock, inp, dest):
        '''
        Helper function to main sending loop. Reads client input and dispatches accordingly
        :return: None
        '''
        global friend_map
        global friend_ip_map
        global server_dest
        global listening
        if inp == '':
            return
        global ACK_recvd
        split_inp = inp.split()
        if(split_inp[0] == 'send' or split_inp[0] == 'send_all'):
            isbroadcast = split_inp[0] == 'send_all'
            if isbroadcast and len(split_inp) == 1:
                return
            if not isbroadcast and len(split_inp) <= 2:
                return
            message = ('send_all ' + ' '.join(split_inp[1:])).encode() if isbroadcast else ' '.join(split_inp[2:]).encode()
            name = None if isbroadcast else split_inp[1]
            if not isbroadcast and name not in friend_map.keys(): 
                util.pmessage('error: invalid name {0}'.format(name), False)
                return
            info = None if isbroadcast else friend_map[name]
            if(isbroadcast or info[2]):
                lock.acquire()
                ACK_recvd = False
                local_SC = ACK_SC
                lock.release()
                if not isbroadcast:
                    util.Send(sock, message, (info[0], info[1]))
                else:
                    notify_server_channel_msg(sock, message, server_dest, local_SC)
                if not isbroadcast and not wait_ACK((info[0], info[1]), local_SC):
                    lock.acquire()
                    local_SC = ACK_SC
                    lock.release()
                    send_save_message(sock, name, message.decode(), local_SC)
            else:
                lock.acquire()
                local_SC = ACK_SC
                ERR_recvd = False
                lock.release()
                send_save_message(sock, name, message.decode(), local_SC)
        
        elif(len(split_inp) == 2 and split_inp[0] == 'dereg'):
            name = split_inp[1]
            lock.acquire()
            local_SC = ACK_SC   #capture global ACK state to wait for ACK in notify_server_leave
            lock.release()
            listening = False
            if name not in friend_ip_map.keys() and name != my_name:
                return
            if notify_server_leave(sock, split_inp[1],server_dest, local_SC):
                util.pmessage('You are Offline. Bye')
            else:
                util.pmessage('Server not responding')
                util.pmessage('Exiting')
        elif(split_inp[0] == 'reg' and len(split_inp) == 2):
            name = split_inp[1]
            if name not in friend_ip_map.keys() and name != my_name:
                return
            reg_to_server(sock, name, server_dest)
            listening = True


def clnt_send(sock, dest):
    '''
    Main loop for sending thread of client. Waits for input from client on infinite loop.
    :return: None
    '''
    while(True):
        util.pmessage('', False)
        inp = input()
        clnt_send_h(sock, inp, dest)

def update_table(fields, display= False):
    '''
    Updates global friend_table w/ information sent by server.
    :return: None
    '''
    global friend_map
    global friend_id_map
    global accept_msg
    friend_map[fields[2]] = (fields[0], int(fields[1]), bool(int(fields[3])))
    friend_ip_map[(fields[0], int(fields[1]))] = (fields[2], bool(int(fields[3])))
    if display:
        util.pmessage(accept_msg)

def clnt_listen(sock):
    '''
    Main function of listening thread. Reads from socket and interprets messages from server and accounts for updates global ACK state.  
    :return: None
    '''
    global ACK_recvd
    global ACK_SC
    global server_dest
    global ERR_recvd
    global listening
    global my_name
    while(True):
        sender_message, sender_address = sock.recvfrom(util.SIZE)
        sender_message = sender_message.decode('UTF-8')
        if(sender_message == str(util.MAGIC_NUM)): #we recieved an ACK
            lock.acquire()
            ACK_recvd = True
            ACK_SC+=1
            update = time.time()
            lock.release()
            continue
        if(sender_message == str(util.MAGIC_NUM)+'E'): #we recieved an error for savesend message
            lock.acquire()
            ERR_recvd = True
            lock.release()
            continue
        split_message = sender_message.split() 
        if split_message[0] == 'TU': #TU, TUW, TUF are all updates on friend table
            update_table(split_message[1:], True)
        elif split_message[0] == 'TUW':
            update_table(split_message[1:], False)
        elif split_message[0] == 'TUF':
            update_table(split_message[1:], False)
        elif sender_message == str(util.MAGIC_NUM) + 'O' and listening:
            send_ACK(sock, server_dest)
        elif split_message[0] == 'MAIL':
            display_mail(sender_message) #display the mail to the client from server once registering
        elif split_message[0] == 'Channel_Message' and listening:
            send_ACK(sock, server_dest, True, my_name)
            util.pmessage(sender_message)
        elif listening: # if we get here we know that this is a message
            name = friend_ip_map[sender_address][0] + ': ' if sender_address != server_dest else ''
            send_ACK(sock, sender_address)
            util.pmessage(name +  sender_message)

def main():
    '''
    Main function : performs setup, intial registration w/ server, starts lisetning and sending threads
    :return: None
    '''
    global server_dest
    global my_name
    if len(sys.argv) != 5:
        util.Die('usage: {0} -c <name> <server-ip> <server-port> <client-port>'.format(util.MAIN_P))
    signal.signal(signal.SIGALRM, timeout_handler)
    server_dest = ( sys.argv[2], util.Port(sys.argv[3]))
    my_name = sys.argv[1]
    my_sock = clnt_setup()
    util.Send(my_sock, str.encode(my_name), server_dest) #initial connection w/ server, send nick name

    send_thread = threading.Thread(target = clnt_send, args = (my_sock, server_dest)) 
    listen_thread = threading.Thread(target = clnt_listen, args = (my_sock, ))

    send_thread.start()
    listen_thread.start()

    send_thread.join()
    listen_thread.join()


if __name__ == '__main__':
    main()

