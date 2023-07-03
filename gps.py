import struct
import binascii
import redis
from datetime import datetime
from crc import crc16
import socket
import codecs
def unpack(fmt, data):
    try:
        return struct.unpack(fmt, data)
    except struct.error:
        flen = struct.calcsize(fmt.replace('*', ''))
        alen = len(data)
        idx = fmt.find('*')
        before_char = fmt[idx-1]
        n = (alen-flen)/struct.calcsize(before_char)+1
        fmt = ''.join((fmt[:idx-1], str(n), before_char, fmt[idx+1:]))
        return struct.unpack(fmt, data)


class GPSTerminal:
    def __init__(self, socket):
        self.socket = socket[0]
        self.ip = socket[1][0]
        self.socket.settimeout(15)
        self.initVariables()

    def initVariables(self):
        self.imei = "unknown"
        self.sensorsDataBlocks = []
        self.error = []
        self.blockCount = 0
        # Raw data bytes from tracker
        self.raw: bytes = ''

        self.success = True
        # Break in data, that was read from socket
        self.dataBreak = 0
        # If we have more than 5 try to read, connection not proceeded
        self.possibleBreakCount = 5


    def startReadData(self):
        try:
            self.proceedConnection()
        except socket.timeout as e:
            print("SOCKET TIMEOUT")
            print(e)
            self.success = False

    def proceedConnection(self):

        #if self.isCorrectConnection():
        self.readIMEI()
        if self.imei:
            print("IMEI: ")
            print(self.imei)
            self.proceedData()
        else:
            print("INCORRECT CONNECTION")
            self.error.append( "Incorrect connection data stream" )
            self.success = False

    def proceedData(self):
        """
        Received and proceed work data of GPS Terminal
        """
        self.time = datetime.now()
        self.data = self.readData()
        if self.data:
            print("DATA" + str(self.data))
            Zeros = self.data[0:3]
            AVLLength = self.data[4:7]
            CodecID = self.data[8:9]
            print("ZEROS: ")
            print(Zeros)
            print("AVL LENGHT:")
            print(AVLLength)
            print(unpack('i',AVLLength))
            print("CODEC ID")
            print(CodecID)
            Zeros, AVLLength, CodecID, BlockCount, Hexline = unpack("sIBBs*", self.data)
            print( "CodecID" + CodecID)
            self.Hexline = binascii.hexlify(Hexline)
            self.blockCount = BlockCount
            print( "BlockCount" +BlockCount)
            self.AVL = 0 # AVL ? Looks like data reading cursor
            proceed = 0
            AVLBlockPos = 0
            while proceed < BlockCount:
                try:
                    data = self.proceedBlockData()
                    print(data)
                    self.sensorsDataBlocks.append( data )
                except ValueError as e:
                    self.dataBreak += 1
                    # In case data consistency problem, we are re-trying to read data from socket
                    self.reReadData(Hexline)
                    # If we have more than possibleBreakCount problems, stop reading
                    if self.dataBreak > self.possibleBreakCount :
                        # After one year we have 0 problem trackers, and +200k that successfully send data after more than one break
                        self.error.append( "Data break" )
                        self.success = False
                        return
                    else:
                        self.AVL = AVLBlockPos
                        # Re try read data from current block
                        proceed -= 1
                proceed += 1
                AVLBlockPos = self.AVL
        else:
             self.error.append( "No data received" )
             self.success = False

    def readData(self, length = 152):
        data = self.socket.recv(length)
        print("READ DATA:")
        print(data)
        print(len(data))
        if(type(data) == bytes):
            print("RAW" + self.raw)
            
            self.raw += data.decode('latin-1')
        else:
            print("RAW STRING")
            self.raw += data.encode()
        return data

    def reReadData(self, Hexline):
        HexlineNew = unpack("s*", self.readData())
        Hexline += HexlineNew[0]
        self.Hexline = binascii.hexlify(Hexline)

    def proceedBlockData(self):
        """
        Proceed block data from received data
        """
        DateV = '0x'+ self.extract(16)
        DateS = round(long( DateV, 16) /1000, 0)
        Prio = self.extract_int(2)
        GpsLon = self.extract_int(8)
        GpsLat = self.extract_int(8)
        Lon = str(float(GpsLon)/10000000)
        Lat = str(float(GpsLat)/10000000)
        GpsH = self.extract_int(4)
        GpsCourse = self.extract_int(4)
        GpsSat = self.extract_int(2)
        GpsSpeed = self.extract_int(4)

        IOEventCode = self.extract_int(2)
        NumOfIO = self.extract_int(2)

        sensorDataResult = {}
        pais_count = 0
        for i in [1,2,4,8]:
            pc = 0
            data = self.readSensorDataBytes(i)
            for iocode in data.keys():
                pais_count+=1
                sensorDataResult[iocode] = data[iocode]
                pc += 1

        return {'imei' : self.imei, 'date': DateS, 'Lon': Lon, 'Lat': Lat, 'GpsSpeed': GpsSpeed, 'GpsCourse': GpsCourse, 'sensorData': sensorDataResult}

    def readSensorDataBytes(self, count):
        result = {}
        pairsCount = self.extract_int(2)
        i = 1
        while i <= pairsCount:
            IOCode = self.extract_int(2)
            IOVal = self.extract_int( count * 2)
            result[IOCode] = IOVal
            i+=1
        return result

    def extract(self, length):
        result = self.Hexline[ self.AVL : (self.AVL + length) ]
        self.AVL += length
        return result

    def extract_int(self, length):
        return int(self.extract(length), 16)

    def readIMEI(self):
        IMEI = self.readData(34)
        self.imei = IMEI
        self.socket.send(struct.pack('i',1))

    def isCorrectConnection(self):
        """
        Check data from client terminal for correct first bytes
        """
        hello = self.readData(2)
        return '(15,)' == str(
            struct.unpack("!H", hello )
        )

    def sendOKClient(self):
        """
        Reply for connected client that data correctly received
        """
        #self.socket.send(bytes(0x01))
        print("BLOCK COUNT" + str(self.blockCount))
        self.socket.send(struct.pack("!L", 1))
        self.closeConnection()

    def sendFalse(self):
        self.socket.send(struct.pack("!L", 0))
        self.closeConnection()

    def closeConnection(self):
        self.socket.close()

    def getSensorData(self):
        return self.sensorsDataBlocks
    def getIp(self):
        return self.ip
    def getImei(self):
        return self.imei
    def isSuccess(self):
        return self.success

