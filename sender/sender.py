import glob
import importlib
import os
import os.path
import re
import serial
import sys
import time

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
            import _winreg
            key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, 'HARDWARE\\DEVICEMAP\\SERIALCOMM')
            while True:
                dev = _winreg.EnumValue(key, len(devices))
                if dev is None:
                    break
                devdesc, devname, _ = dev
                devices.append((str(devname), str(devdesc)))
        print self.devices
        
class SerialLineReader:
    def __init__(self, device = None, speed = 115200):
        if device is None or device[0:1] == '=':
            finder = SerialDeviceFinder()
            if len(finder.devices) == 0:
                raise Exception, "No serial devices found"
            if device is None:
                device = finder.devices[-1][0]
            else:
                m = re.compile(device[1:], re.I)
                matched = [name for name, description in sorted(finder.devices) if m.search(name)]
                if len(matched) == 0:
                    matched = [name for name, description in sorted(finder.devices) if m.search(description)]
                    if len(matched) == 0:
                        raise Exception, "No serial devices found matching pattern %s" % device[1:]
                device = matched[0]
        self.ser = serial.Serial(device, speed, timeout=0.01)
        self.data = ''
    def write(self, data):
        self.ser.write(data)
        #self.ser.flush()
    def writeln(self, data):
        self.write(data + "\n")
    def poll(self):
        buf = self.ser.read(1024)
        self.data += buf
        while True:
            pos = self.data.find('\n')
            if pos != -1:
                line = self.data[0:pos]
                self.data = self.data[pos + 1:]
                if line.endswith('\r'):
                    line = line[:-1]
                return line
            else:
                return None

class GrblStateMachine:
    def __init__(self, *args, **kwargs):
        self.reader = SerialLineReader(*args, **kwargs)
        self.wait_for_banner()
    def wait_for_banner(self):
        self.banner_time = time.time()
        self.sent_status_request = False
        self.outqueue = []
        self.maxbytes = 80
        self.process_cooked_status('Connecting', {})
    def send_line(self, line, context = None):
        if self.banner_time is not None:
            return "Device has not reported yet"
        line = line.strip()
        while sum(map((lambda lineandcontext: len(lineandcontext[0])), self.outqueue)) + len(self.outqueue) + len(line) + 1 > self.maxbytes:
            if not self.handle_input():
                return "Device busy"
        print "Sending: %s" % line
        self.outqueue.append((line, context))
        self.reader.writeln(line)
    def handle_line(self, inp):
        if self.banner_time is not None and inp.find('Grbl') != -1:
            self.banner_time = None
            return True
        if inp.startswith('<') and inp.endswith('>'):
            self.banner_time = None
            self.process_status(inp)
            return True
        if self.banner_time is not None:
            # ignore line garbage
            return True
        if inp.startswith('error:'):
            print "Error Pop: %s, %s" % (self.outqueue[0], inp)
            self.error(self.outqueue[0][0], self.outqueue[0][1], inp[7:])
            self.outqueue.pop(0)
            return True
        if inp == 'ok':
            print "Pop: %s" % (self.outqueue[0], )
            self.confirm(*self.outqueue[0])
            self.outqueue.pop(0)
            return True
        if inp[0] == '[' and inp[-1] == ']':
            if ':' in inp:
                par, values = inp[1:-1].split(":", 1)
                self.handle_gcode_parameter(par, values)
            else:
                self.handle_gcode_state(inp[1:-1].split(" "))
            return True
        if inp[0] == '$':
            var, value = inp.split('=', 1)
            comment = ''
            if value.find(' (') != -1:
                value, comment = value.split(' (', 1)
                if len(comment) and comment[-1] == ')':
                    comment = comment[:-1]
            self.handle_variable_value(var, value, comment)
            return True
        raise ValueError, "Unexpected input: %s" % inp
    def handle_input(self):
        inp = self.reader.poll()
        if inp is not None:
            return self.handle_line(inp)
        if self.banner_time is None:
            if len(self.outqueue):
                print "Unconfirmed: %s" % self.outqueue
            return False
        dtime = time.time() - self.banner_time
        if not self.sent_status_request:
            if dtime > 2:
                self.ask_for_status()
                self.sent_status_request = True
        elif dtime > 10:
            self.process_cooked_status('Connect Timeout', {})
        return False
    def handle_variable_value(self, var, value, comment):
        print "%s -> %s (%s)" % (var, value, comment)
    def handle_gcode_parameter(self, par, values):
        print "%s -> %s" % (par, values)
    def handle_gcode_state(self, values):
        print "%s" % (", ".join(values))

    def flush(self):
        while len(outqueue):
            if not self.handle_input():
                time.sleep(0.05)
                continue
    def confirm(self, line, context):
        pass
    def process_status(self, response):
        if response[0] == '<' and response[-1] == '>':
            status, params = response[1:-1].split(",", 1)
            cooked = {}
            for kw, value in re.findall(r'([A-Za-z]+):([0-9.,-]+)', params):
                value = value.rstrip(',')
                cooked[kw] = map(float, value.split(","))
            self.process_cooked_status(status, cooked)
        else:
            raise ValueError, "Malformed status: %s" % response
    def process_cooked_status(self, status, params):
        print status, params
    def ask_for_status(self):
        self.reader.write('?')
    def pause(self):
        self.reader.write('!')
    def restart(self):
        self.reader.write('~')
    def soft_reset(self):
        self.reader.write('\x18')
        self.wait_for_banner()
    def close(self):
        self.reader.close()
        self.reader = None

if __name__ == '__main__':
    sm = GrblStateMachine()

    t = time.time()
    f = open(sys.argv[1], "r")
    for line in f:
        sm.send_line(line)

    print "Total time elapsed: %0.2s" % (time.time() - t)
