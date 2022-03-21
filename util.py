import sys

SIZE = 4096
PROMPT = '>>'
MAIN_P = 'chatter.py'
MAGIC_NUM = 52


class TimoutException(Exception):
    pass

def Die(message):
    print('error: {0}'.format(message))
    sys.exit()

def pmessage(message, brackets=True):
    if(brackets):
        print('\n'+PROMPT + ' [' + str(message)+']\n'+PROMPT + ' ', end ='')
    else:
        print(PROMPT + ' ' + message, end = ' ')
        sys.stdout.flush()

def Port(p):
    try: 
        port = int(p)
        if(port < 1024 or port > 65535):
            raise ValueError
    except ValueError as ve:
        Die('invalid port number {0}'.format(p))
    return port

def Send(socket, message, dest_addr):
    try:
        socket.sendto(message, dest_addr)
    except Exception as e:
        Die(str(e) + ' unable to send message to ({0}, {1})'.format(dest_addr[0], dest_addr[1]))
