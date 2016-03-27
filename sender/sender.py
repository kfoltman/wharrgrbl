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
                try:
                    dev = _winreg.EnumValue(key, len(self.devices))
                except:
                    break
                devdesc, devname, _ = dev
                self.devices.append((str(devname), str(devdesc)))
        print self.devices
        
class SerialLineReader:
    def __init__(self, device = None, speed = 115200):
        self.device = device
        self.speed = speed
        self.open_device(self.device, self.speed)
    def open_device(self, device, speed):
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
        try:
            buf = self.ser.read(1024)
        except:
            return None
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
    def close(self):
        if self.ser is not None:
            self.ser.close()

class GrblStateMachine:
    def __init__(self, *args, **kwargs):
        self.reader = SerialLineReader(*args, **kwargs)
        self.position_queries = 0
        self.last_status = 0
        self.last_cmd = None
        self.outqueue = []
        self.wait_for_banner(True)
    def wait_for_banner(self, first):
        self.banner_time = time.time()
        self.sent_status_request = False
        self.maxbytes = 80
        self.process_cooked_status('Connecting' if first else 'Resetting', {})
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
        if inp.startswith('<') and inp.endswith('>'):
            self.position_queries -= 1
            self.process_status(inp)
            return True
        if inp[0:7] == 'ALARM: ':
            print "Outqueue = %s, last_cmd = %s" % (repr(self.outqueue), repr(self.last_cmd))
            if len(self.outqueue):
                self.alarm(self.outqueue[0][0], self.outqueue[0][1], inp[7:])
            else:
                self.alarm(self.last_cmd[0], self.last_cmd[1], inp[7:])
            return True
        if self.banner_time is not None and inp.startswith("Grbl "):
            self.banner_time = None
            self.outqueue[:] = []
            return True
        if self.banner_time is not None:
            if inp != '':
                print "(ignore line garbage, banner time = %s)" % self.banner_time
            # ignore line garbage
            return True
        if inp.startswith('error:'):
            print "Error Pop: %s, %s" % (self.outqueue[0], inp)
            self.error(self.outqueue[0][0], self.outqueue[0][1], inp[7:])
            self.outqueue.pop(0)
            return True
        if inp == '':
            return True
        if inp == 'ok':
            print "Pop: %s" % (self.outqueue[0], )
            self.confirm(*self.outqueue[0])
            self.last_cmd = self.outqueue.pop(0)
            return True
        if inp[0] == '[' and inp[-1] == ']':
            if ':' in inp:
                par, values = inp[1:-1].split(":", 1)
                self.handle_gcode_parameter(par, values.strip())
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
    def alarm(self, line, context, message):
        print "Alarm pop: %s - %s" % (line, message)
    def process_status(self, response):
        if response[0] == '<' and response[-1] == '>':
            self.last_status = time.time()
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
        self.position_queries += 1
        self.reader.write('?')
    def ask_for_status_if_idle(self):
        if self.position_queries > 0 and time.time() > self.last_status + 1:
            self.position_queries -= 1
            if self.position_queries > 0 and time.time() > self.last_status + 5:
                self.position_queries = 0
        if self.banner_time is None and (self.position_queries <= 0):
            self.position_queries = 0
            self.ask_for_status()
    def pause(self):
        self.reader.write('!')
    def restart(self):
        self.reader.write('~')
    def soft_reset(self):
        self.reader.write('\x18')
        self.wait_for_banner(False)
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
