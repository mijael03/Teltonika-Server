import socket
import threading

from time import gmtime, strftime
from configparser import RawConfigParser
from optparse import OptionParser

from gps import GPSTerminal

class ClientThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None, *args, **kwargs):
        threading.Thread.__init__(self)
        self.socket = kwargs['socket']
        self.config = kwargs['config']
        self.logTime = strftime("%d %b %H:%M:%S", gmtime())
        self.identifier = "None"
        
        #self.rcli = redis.Redis(host=r_host, port=r_port, db=r_db)
        
    
    def log(self, msg):
        print("%s\t%s\t%s"%(self.logTime, self.identifier, msg))
        pass

    def run(self):
        client = self.socket
        if client:
            terminalClient = GPSTerminal(self.socket)
            self.identifier = terminalClient.getIp()
            terminalClient.startReadData()
            #terminalClient.sendOKClient()

            if terminalClient.isSuccess():
                #self.saveData(terminalClient.getSensorData())
                #terminalClient.sendOKClient()
                self.log('Client %s'%terminalClient.getImei())
                pass
            else:
                terminalClient.sendFalse()
                pass
            terminalClient.closeConnection()
        else: 
            self.log('Socket is null.')

    def saveData(self, sensorData):
        print("DATA ")
        print(len(sensorData))
        #self.rcli.rpush(self.channel, pickle.dumps(sensorData))

def get_config(config_file):

    config = RawConfigParser()

    config.add_section('server')
    config.set('server', 'port', '9980')
    config.read(config_file)
    return config

if __name__ == "__main__":

    optParser = OptionParser()
    optParser.add_option("-c", "--config", dest="conf_file", help="Config file", default="gps.conf")
    (options, args) = optParser.parse_args()

    config = get_config(options.conf_file)

    print("Gps sensors server. %s" % strftime("%d %b %H:%M:%S", gmtime()))
    print("Config: %s" % options.conf_file)
    print("Server started at port %d" % int(config.get('server', 'port')))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', int(config.get('server', 'port'))))
    server.listen(5)

    while True:
        ClientThread(socket=server.accept(), config = config).start()

