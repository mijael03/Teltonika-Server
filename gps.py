import json
import struct
import binascii
from datetime import datetime
from crc import crc16
import socket
import data_exceptions
def bin_to_float( binary):
        return struct.unpack('!f',struct.pack('!I', int(binary, 2)))[0]
def unpack(fmt, data):
    try:
        return struct.unpack(fmt, data)
    except struct.error:
        print("FMT: " + fmt)
        flen = struct.calcsize(fmt.replace('*', ''))
        alen = len(data)
        print(alen)
        idx = fmt.find('*')
        before_char = fmt[idx-1]
        n = (alen-flen)/struct.calcsize(before_char)+1
        fmt = ''.join((fmt[:idx-1], str(int(n)), before_char, fmt[idx+1:]))
        print("FMT")
        print(fmt)
        return struct.unpack(fmt, data)
class GPSTerminal:
    def __init__(self, socket):
        self.socket = socket[0]
        self.ip = socket[1][0]
        self.socket.settimeout(10)
        self.initVariables()
    def initVariables(self):
        self.imei = "unknown"
        self.numberRecords: bytes = ''
        self.sensorsDataBlocks = []
        self.error = []
        self.blockCount = 0
        self.blockCountBytes: bytes = ''
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
            #self.proceedConexion()
        except socket.timeout as e:
            print("SOCKET TIMEOUT")
            print(e)
            self.success = False
    def proceedConnection(self):
        if self.isCorrectConnection():
            self.readIMEI()
            if self.imei:
                print("IMEI: ")
                print(self.imei)
                print(type(self.imei))
                print()
                self.proceedData()
            else:
                print("INCORRECT CONNECTION")
                self.error.append( "Incorrect connection data stream" )
                self.success = False
        else:
            print("The size is not correct")
    def proceedConexion(self):
        self.readIMEI()
        while True:
            #self.readIMEI()
            if self.imei:
                try:
                    self.proceedData()
                    #time.sleep(2)
                    self.sendOKClient()
                except data_exceptions.DataNotReceivedException:
                    print("Los datos no han sido recibidos")
                    #self.closeConnection()
                    break
            else:
                print("INCORRECT CONNECTION")
                self.error.append( "Incorrect connection data stream" )
                self.success = False
                break
    def proceedData(self):
        """
        Received and proceed work data of GPS Terminal
        """
        self.time = datetime.now()
        self.data = self.readData()
        if self.data:
            dataLen = len(self.data)
            if dataLen > 44:
                Zeros, AVLLength, CodecID, BlockCount, Hexline, BlockCount2, CRC_16 = unpack('4sIBBs*B4s', self.data)
                self.blockCountBytes = self.data[9:10]
                preamble = int.from_bytes(Zeros)
                if(preamble == 0):
                    print(type(self.data[9:-4]))
                    print(self.data[9:-4][:1])
                    self.Hexline = binascii.hexlify(Hexline)
                    crc16Calculated = crc16(self.data[8:-4])
                    crc16value = int.from_bytes(CRC_16)
                    if BlockCount == BlockCount2:
                        if crc16Calculated == crc16value:
                            with open("logs.txt", "a") as file_object:
                                file_object.write(f'HEADER FOR RECORDS RECEIVED in : {self.time}  for imei {self.imei} \n')
                                file_object.write(f'AVL LENGTH: {AVLLength} \n')
                                file_object.write(f'CODEC ID : {CodecID} \n')
                                file_object.write(f'QUantity 1: {BlockCount} \n')
                                file_object.write(f'QUantity 2: {BlockCount2} \n')
                                file_object.write(f'CRC-16 : {CRC_16} \n')
                            self.blockCount = BlockCount
                            self.AVL = 0 # AVL ? Looks like data reading cursor
                            proceed = 0
                            AVLBlockPos = 0
                            json_array = []
                            while proceed < BlockCount:
                                try:
                                    print("PROCEED")
                                    print(proceed)
                                    data = self.proceedBlockData()
                                    print(data)
                                    json_array.append(data)
                                    self.sensorsDataBlocks.append(data)
                                except ValueError as e:
                                    print(f'ERROR + {e}')
                                    self.dataBreak += 1
                                    # In case data consistency problem, we are re-trying to read data from socket
                                    self.reReadData(Hexline)
                                    # If we have more than possibleBreakCount problems, stop reading
                                    if self.dataBreak > self.possibleBreakCount :
                                        # After one year we have 0 problem trackers, and +200k that successfully send data after more than one break
                                        print("ERROR")
                                        self.error.append( "Data break" )
                                        self.success = False
                                        return
                                    else:
                                        self.AVL = AVLBlockPos
                                        # Re try read data from current block
                                        proceed -= 1
                                proceed += 1
                                AVLBlockPos = self.AVL
                            json_array_sorted = sorted(json_array, key=lambda d: d['date'])
                            with open("logs.txt", "a", encoding='utf-8') as file_object:
                                # Append 'hello' at the end of file
                                file_object.write(f'RECORD RECEIVED')
                                file_object.write("\n")
                                file_object.write(json.dumps(json_array_sorted,indent=4))
                                file_object.write("\n")
                        else:
                            print("CRC-16 do not match")
                            self.success = False
                    else:
                        print("Number of records do not match")
                        self.success = False
                else:
                    print("Preamble should be 0")
            else:
                print(f'Minimum size for AVL Data Packet is 45, the size of the packet received is {dataLen}')
        else:
            print("ERRROR :(")
            self.error.append( "No data received" )
            self.success = False
            raise data_exceptions.DataNotReceivedException
    def readData(self, length = 1280):
        data = self.socket.recv(length)
        print("READ DATA:")
        print(data.hex())
        print(len(data))
        if(type(data) == bytes):
            self.raw += data.decode('latin-1')
        else:
            print("RAW STRING")
            self.raw += data.encode()
        return data
    def reReadData(self, Hexline):
        print('REREAD DATA')
        HexlineNew = unpack("s*", self.readData())
        Hexline += HexlineNew[0]
        self.Hexline = binascii.hexlify(Hexline)
    def proceedBlockData(self):
        """
        Proceed block data from received data
        """
        print("INICIO BLOCK DATA")
        #DateV = b'0x' + self.extract(16)
        DateV = self.extract(16)
        DateS = round(int(DateV, 16) /1000, 0)
        Prio = self.extract_int(2)
        #GpsLon = self.extract_int(8)
        GpsLon = self.extract_coordinates(8)
        #GpsLat = self.extract_int(8)
        GpsLat = self.extract_coordinates(8)
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
        sensorDataResultSorted = {key:value for key, value in sorted(sensorDataResult.items(), key=lambda item: int(item[0]))}
        print(str(self.imei))
        return {'imei' : self.imei, 'date': DateS, 'Lon': Lon, 'Lat': Lat, 'Satellites':GpsSat, 'Prio': Prio, 'GPS H': GpsH, 'GpsSpeed': GpsSpeed, 'GpsCourse': GpsCourse, 'IO EVENT CODEE': IOEventCode, 'Number of IO': NumOfIO, 'sensorData': sensorDataResultSorted}
        #return {'imei' : self.imei, 'date': DateS, 'Lon': Lon, 'Lat': Lat, 'GpsSpeed': GpsSpeed, 'GpsCourse': GpsCourse}
    def readSensorDataBytes(self, count):
        result = {}
       #print(f'FIRST: {self.extract_int( 2 + ( count * 2 ))}')
        pairsCount = self.extract_int(2)
        i = 1
        while i <= pairsCount:
            IOCode = self.extract_int(2)
            #print(f'IOCODE {IOCode}')
            IOVal = self.extract_int( count * 2)
            #print(f'IOVAL {IOVal} - count {count}')
            result[IOCode] = IOVal
            i+=1
        return result
    def extract(self, length):
        result = self.Hexline[ self.AVL:(self.AVL + length) ]
        self.AVL += length
        return result
    def extract_int(self, length):
        try:
            return int(self.extract(length),16)
        except:
            return 0
    def extract_coordinates(self, length):
        result =  self.extract(length)
        print("RESULT")
        intresult = int(result, base= 16)
        binaryresult = bin(int(result, base= 16))
        binresult = binaryresult[2:]
        isNegative = int(binresult[0:1],2) == 1
        if(intresult != 0):
            if(intresult & ( 1 << 31)):
                print("really negative")
                print(isNegative)
                intresult -= 1 << 32
            else:
                intresult = 1 << 32
            return intresult
        else:
            return 0
    def readIMEI(self):
        IMEI = self.readData(34)
        print(len(IMEI))
        try:
            self.imei = IMEI.decode('utf-8')[2:]
        except Exception as e:
            print("EXCEPCION")
            print(e)
            print(IMEI)
        accept_con_mes = '\x01'
        self.socket.send(accept_con_mes.encode('utf-8'))
    def isCorrectConnection(self):
        """
        Check data from client terminal for correct first bytes
        """
        hello = self.readData(2)
        print("FIRS TWO BYTES")
        print(hello)
        firstTwoBytes = str(
            struct.unpack("!H", hello )
        )
        return '(15,)'  == firstTwoBytes or  '(16,)' == firstTwoBytes
    def sendOKClient(self):
        """
        Reply for connected client that data correctly received
        """
        #self.socket.send(struct.pack("!L", self.blockCount))
        #self.socket.send(struct.pack("i", self.blockCount))
        self.socket.send(self.blockCount.to_bytes())
        print("BLOCK COUNT " + str(self.blockCount))
        #self.socket.send(struct.pack("!L", 1))
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