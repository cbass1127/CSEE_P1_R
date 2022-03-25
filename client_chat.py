import sys
import util
import os
import socket
import threading
import signal
import time


#accept_msg = 'Client table updated.'
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


def send_ACK(socket, addr, use_name = False, name = ''):
    if not use_name:
        util.Send(socket, str(util.MAGIC_NUM).encode(), addr)
    else:
        s = str(util.MAGIC_NUM) + ' ' + name
        util.Send(socket, s.encode(), addr)

def timeout_handler(signum, frame):
    raise util.timoutexception('timout!')

def wait_ACK_h(local_SC):
    global ACK_SC
    while(local_SC == ACK_SC):
        pass


def wait_ACK(send_addr, local_SC, client = True, duration = 0.5):
    global ACK_recvd
    global ACK_SC
    name = ''
    if client:
        name = friend_ip_map[(send_addr[0], send_addr[1])][0]
#    signal.alarm(1)
#    try:
#        #signal.setitimer(signal.ITIMER_REAL, 0.5)
#        wait_ACK_h(local_SC)
#        #signal.setitimer(signal.ITIMER_REAL, 0)
#        signal.alarm(0)
#        util.pmessage('Message recieved by ' + name +'.')
#        return True
#    except Exception as e:
#        if client:
#            friend_ip_map[(send_addr[0], send_addr[1])] = (name ,False)
#            util.pmessage(' No ACK from ' + name + ' ,message sent to server.')
#        #signal.setitimer(signal.ITIMER_REAL, 0)
#        signal.alarm(0)
#        return False

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
    s = 'dereg ' + name
    util.Send(sock, s.encode(), addr)


def notify_server_leave(sock, name, send_addr, local_SC):
    count = 0
    status = False
    while(count < 6 and (not status)):
        notify_leave(sock, name, send_addr)
        status = wait_ACK(send_addr, local_SC, False)
        count+=1
    return status

def notify_server_channel_msg(sock, message, send_addr, local_SC):
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
    my_port = util.Port(sys.argv[4]) 
    clnt_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); 
    clnt_sock.bind(('0.0.0.0', my_port))
    return clnt_sock


def reg_to_server(sock, name, addr):
    s = str(util.MAGIC_NUM) + 'R' + ' ' + name
    send_s = s.encode()
    util.Send(sock, send_s, addr)

def display_mail(messages):
    util.pmessage('YOU HAVE MESSAGES')
    lines = messages.split('\n') 
    for line in lines:
        if line.strip() != '':
            util.pmessage(line + '\n', False)

#def add_client(address, port, name)::
#    online_status = True
#    client_ips[address] = 1
#    client_map[(address, port)] = (name, online_status)
#    util.pmessage(accept_msg)
#
def clnt_send_h(sock, inp, dest):
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
            message = ('send_all ' + ' '.join(split_inp[1:])).encode() if isbroadcast else ' '.join(split_inp[2:]).encode()
            name = None if isbroadcast else split_inp[1]
            info = None if isbroadcast else friend_map[name]
            if not isbroadcast and name not in friend_map.keys(): 
                util.pmessage('error: invalid name {0}'.format(name), False)
                return
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
        
        elif(split_inp[0] == 'dereg'):
            lock.acquire()
            local_SC = ACK_SC
            lock.release()
            listening = False
            if notify_server_leave(sock, split_inp[1],server_dest, local_SC):
                util.pmessage('You are Offline. Bye')
            else:
                util.pmessage('Server not responding')
                util.pmessage('Exiting')
        elif(split_inp[0] == 'reg' and len(split_inp) == 2):
            name = split_inp[1]
            reg_to_server(sock, name, server_dest)
            listening = True


def clnt_send(sock, dest):
    while(True):
        util.pmessage('', False)
        inp = input()
        clnt_send_h(sock, inp, dest)

def update_table(fields):
    global friend_map
    global friend_id_map
    friend_map[fields[2]] = (fields[0], int(fields[1]), bool(int(fields[3])))
    friend_ip_map[(fields[0], int(fields[1]))] = (fields[2], bool(int(fields[3])))



def clnt_listen(sock):
    global ACK_recvd
    global ACK_SC
    global server_dest
    global ERR_recvd
    global listening
    while(True):
        sender_message, sender_address = sock.recvfrom(util.SIZE)
        sender_message = sender_message.decode('UTF-8')
        if(sender_message == str(util.MAGIC_NUM)):
            lock.acquire()
            ACK_recvd = True
            ACK_SC+=1
            update = time.time()
       #     print('ACK UPDATED ',ACK_SC , ' ', update)
            lock.release()
            continue
        if(sender_message == str(util.MAGIC_NUM)+'E'):
            lock.acquire()
            ERR_recvd = True
            lock.release()
            continue
        split_message = sender_message.split() 
        if split_message[0] == 'TU':
            update_table(split_message[1:])
        elif sender_message == str(util.MAGIC_NUM) + 'O':
            send_ACK(sock, server_dest)
        elif split_message[0] == 'MAIL':
            display_mail(sender_message) #display the mail to the client 
        elif split_message[0] == 'Channel_Message' and listening:
            send_ACK(sock, server_dest, True, my_name)
            util.pmessage(sender_message)
        elif listening:
            name = friend_ip_map[sender_address][0] + ': ' if sender_address != server_dest else ''
            send_ACK(sock, sender_address)
            util.pmessage(name +  sender_message)

def main():
    global server_dest
    global my_name
    if len(sys.argv) != 5:
        util.Die('usage: {0} -c <name> <server-ip> <server-port> <client-port>'.format(util.MAIN_P))
    signal.signal(signal.SIGALRM, timeout_handler)
    server_dest = ( sys.argv[2], util.Port(sys.argv[3]))
    my_name = sys.argv[1]
    my_sock = clnt_setup()
    util.Send(my_sock, str.encode(my_name), server_dest)

    send_thread = threading.Thread(target = clnt_send, args = (my_sock, server_dest))
    listen_thread = threading.Thread(target = clnt_listen, args = (my_sock, ))

    send_thread.start()
    listen_thread.start()

    send_thread.join()
    listen_thread.join()


if __name__ == '__main__':
    main()

