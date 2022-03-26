import sys
import os
import util

_CLIENT = 'client_chat.py'
_SERVER = 'server_chat.py'

def main():
    '''
    Runs chatApp program. -c if for client and -s is for server.
    :return: None
    '''
    if(sys.argv[1] == '-c' and len(sys.argv) == 6):
        os.system('python3 ' + _CLIENT + ' ' + sys.argv[2] + ' ' + sys.argv[3] + ' ' + sys.argv[4] + ' ' + sys.argv[5])
    elif(sys.argv[1] == '-s' and len(sys.argv) == 3):
        os.system('python3 '+ _SERVER + ' ' + sys.argv[2])
    else:
        util.pmessage('client usage: {0} -c <name> <server-ip> <server-port> <client-port>'.format(util.MAIN_P))
        util.pmessage('server usage: {0} -s <server-port> '.format(util.MAIN_P))
if __name__ == '__main__':
    main()
