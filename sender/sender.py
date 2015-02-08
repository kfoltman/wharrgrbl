import re
import serial
import sys
import time

class SerialLineReader:
    def __init__(self, device = '/dev/ttyUSB0', speed = 115200):
        self.ser = serial.Serial(device, speed, timeout=0.01)
        self.data = ''
    def write(self, data):
        self.ser.write(data)
        #self.ser.flush()
    def writeln(self, data):
        self.write(data + "\n")
    def poll(self):
        buf = self.ser.read(100)
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
