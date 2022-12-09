import glob
import os
import os.path
import re
import serial
import socket

class SerialDeviceFinder:
    def __init__(self):
        self.devices = []
        if os.name == 'posix':
            for fn in glob.glob('/dev/serial/by-id/*'):
                if os.path.islink(fn):
                    path = os.path.join(os.path.dirname(fn), os.readlink(fn))
                    self.devices.append((os.path.abspath(path), os.path.basename(fn)))
                else:
                    self.devices.append((fn, os.path.basename(fn)))
        if os.name == 'nt':
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'HARDWARE\\DEVICEMAP\\SERIALCOMM')
                while True:
                    try:
                        dev = winreg.EnumValue(key, len(self.devices))
                    except:
                        break
                    devdesc, devname, _ = dev
                    self.devices.append((str(devname), str(devdesc)))
            except:
                pass
        
class ReaderBase:
    def writeln(self, data):
        self.write(data + "\n")
    def poll(self):
        buf = self.read(1024)
        if buf is None:
            return None
        self.data += buf
        while True:
            pos = self.data.find(b'\n')
            if pos != -1:
                line = self.data[0:pos]
                self.data = self.data[pos + 1:]
                if line.endswith(b'\r'):
                    line = line[:-1]
                return line
            else:
                return None

class SocketReader(ReaderBase):
    def __init__(self, addr):
        host, port = addr.split(":")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, int(port)))
        self.data = b''
    def is_open(self):
        return True
    def write(self, data):
        return self.socket.send(data)
    def read(self, nbytes):
        return self.socket.recv(nbytes, socket.MSG_DONTWAIT)
    def close(self):
        self.socket.close()
        
class SerialLineReader(ReaderBase):
    def __init__(self, device = None, speed = 115200):
        self.device = device
        self.speed = speed
        self.open_device(self.device, self.speed)
    def open_device(self, device, speed):
        if device is None or device[0:1] == '=':
            finder = SerialDeviceFinder()
            if len(finder.devices) == 0:
                self.ser = None
                self.data = b''
                return
            if device is None:
                device = finder.devices[-1][0]
            else:
                m = re.compile(device[1:], re.I)
                matched = [name for name, description in sorted(finder.devices) if m.search(name)]
                if len(matched) == 0:
                    matched = [name for name, description in sorted(finder.devices) if m.search(description)]
                    if len(matched) == 0:
                        raise Exception("No serial devices found matching pattern %s" % device[1:])
                device = matched[0]
        try:
            self.ser = serial.Serial(device, speed, timeout=0.01)
        except serial.SerialException as e:
            self.ser = None
        self.data = b''
    def is_open(self):
        return self.ser is not None
    def write(self, data):
        self.ser.write(data)
        #self.ser.flush()
    def read(self, nbytes):
        return self.ser.read(nbytes)
    def close(self):
        if self.ser is not None:
            self.ser.close()

