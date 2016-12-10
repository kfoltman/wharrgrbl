import csv
import importlib
import os
import os.path
import re
import sys
import time
from ser_device import *

class GrblVersion(object):
    def __init__(self, name):
        self.name = name

class GrblClassicVersion(GrblVersion):
    def __init__(self, name):
        GrblVersion.__init__(self, name)
    def process_status(self, parent, response):
        if response[0] == '<' and response[-1] == '>':
            status, params = response[1:-1].split("|", 1)
            cooked = {}
            for kw, value in re.findall(r'([A-Za-z]+):([0-9.,-]+)', params):
                value = value.rstrip(',')
                cooked[kw] = map(float, value.split(","))
            parent.process_cooked_status(status, cooked)
        else:
            raise ValueError, "Malformed status: %s" % response
    def parse_variable_value(self, inp):
        var, value = inp.split('=', 1)
        comment = ''
        if value.find(' (') != -1:
            value, comment = value.split(' (', 1)
            if len(comment) and comment[-1] == ')':
                comment = comment[:-1]
        return var, value, comment
    def parse_alarm(self, inp):
        return inp[7:]

class GrblModernVersion(GrblVersion):
    def __init__(self, name):
        GrblVersion.__init__(self, name)
        self.wco = [0, 0, 0]
        self.config_legend = {
        }
        with open("grbl_csv/setting_codes_en_US.csv", "r") as cfg_csv:
            reader = csv.reader(cfg_csv)
            reader.next()
            for row in reader:
                self.config_legend[int(row[0])] = "%s (%s): %s" % tuple(row[1:])
        self.alarms = {
            1 : "Hard limit",
            2 : "Soft limit",
            3 : "Abort during cycle",
            4 : "Probe fail - short",
            5 : "Probe fail - timeout",
            6 : "Homing fail - reset",
            7 : "Homing fail - safety",
            8 : "Homing fail - pull-off failed",
            9 : "Homing fail - no switch",
        }
    def process_status(self, parent, response):
        if response[0] == '<' and response[-1] == '>':
            #print response
            status, params = response[1:-1].split("|", 1)
            cooked = {}
            for param in params.split("|"):
                for kw, value in re.findall(r'([A-Za-z]+):([0-9.,-]+)', param):
                    value = value.rstrip(',')
                    cooked[kw] = map(float, value.split(","))
            #print status, cooked
            if 'WCO' in cooked:
                self.wco = cooked['WCO']
                del cooked['WCO']
            cooked['WPos'] = [cooked['MPos'][i] - self.wco[i] for i in xrange(3)]
            parent.process_cooked_status(status, cooked)
        else:
            raise ValueError, "Malformed status: %s" % response
    def parse_variable_value(self, inp):
        var, value = inp.split('=', 1)
        if var[0] == '$':
            vv = int(var[1:])
            comment = self.config_legend[vv] if vv in self.config_legend else ''
        return var, value, comment
    def parse_alarm(self, inp):
        try:
            alvalue = int(inp[6:])
            return self.alarms[alvalue]
        except:
            return "Unknown alarm"

def create_grbl_version(version):
    if version.startswith("1."):
        return GrblModernVersion(version)
    else:
        return GrblClassicVersion(version)

class GrblStateMachine:
    def __init__(self, *args, **kwargs):
        if os.getenv("TCPGRBL"):
            self.reader = SocketReader(os.getenv("TCPGRBL"))
            # do a soft reset just in case of weird state
        else:
            self.reader = SerialLineReader(*args, **kwargs)
        self.reader.write('\x18')
        self.position_queries = 0
        self.last_status = 0
        self.last_cmd = None
        self.outqueue = []
        self.version = None
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
        if self.banner_time is not None:
            if inp.startswith("Grbl "):
                words = inp.split(" ", 2)
                if len(words) == 3:
                    self.version = create_grbl_version(words[1])
                    print "Version: %s" % self.version
                    self.banner_time = None
                    self.outqueue[:] = []
                    self.position_queries = 0
                else:
                    print "(ignore line garbage %s, banner time = %s)" % (inp, self.banner_time)
            else:
                if inp != '':
                    print "(ignore line garbage %s, banner time = %s)" % (inp, self.banner_time)
                # ignore line garbage
            return True
        if not self.version:
            print "No version set - ignoring %s" % repr(inp)
            return
        if inp.startswith('<') and inp.endswith('>'):
            self.position_queries -= 1
            self.version.process_status(self, inp)
            return True
        if inp[0:6] == 'ALARM:':
            msg = self.version.parse_alarm(inp)
            print "Outqueue = %s, last_cmd = %s" % (repr(self.outqueue), repr(self.last_cmd))
            if len(self.outqueue):
                self.alarm(self.outqueue[0][0], self.outqueue[0][1], msg)
            else:
                self.alarm(self.last_cmd[0], self.last_cmd[1], msg)
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
            var, value, comment = self.version.parse_variable_value(inp)
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
