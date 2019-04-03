#!/usr/bin/python
# coding=utf-8
# "DATASHEET": http://cl.ly/ekot
# https://gist.github.com/kadamski/92653913a53baf9dd1a8
from __future__ import print_function
import serial, struct, sys, time, json
from datetime import datetime
from geopy import geocoders
import aqi
from datetime import datetime, timedelta
import Adafruit_DHT
#from apscheduler.schedulers.blocking import BlockingScheduler
timest = datetime.now() + timedelta(hours=0)
#print(timest)
DEBUG = 0
CMD_MODE = 2
CMD_QUERY_DATA = 4
CMD_DEVICE_ID = 5
CMD_SLEEP = 6
CMD_FIRMWARE = 7
CMD_WORKING_PERIOD = 8
MODE_ACTIVE = 0
MODE_QUERY = 1

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600

ser.open()
ser.flushInput()

byte, data = 0, ""

def dump(d, prefix=''):
    print(prefix + ' '.join(x.encode('hex') for x in d))

def construct_command(cmd, data=[]):
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, '> ')
    return ret

def process_data(d):
    r = struct.unpack('<HHxxBB', d[2:])
    pm25 = r[0]/10.0
    pm10 = r[1]/10.0
    checksum = sum(ord(v) for v in d[2:8])%256
    return [pm25, pm10]
    #print("PM 2.5: {} μg/m^3  PM 10: {} μg/m^3 CRC={}".format(pm25, pm10, "OK" if (checksum==r[2] and r[3]==0xab) else "NOK"))

def process_version(d):
    r = struct.unpack('<BBBHBB', d[3:])
    checksum = sum(ord(v) for v in d[2:8])%256
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))

def read_response():
    byte = 0
    while byte != "\xaa":
        byte = ser.read(size=1)

    d = ser.read(size=9)

    if DEBUG:
        dump(d, '< ')
    return byte + d

def cmd_set_mode(mode=MODE_QUERY):
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    values = []
    if d[1] == "\xc0":
        values = process_data(d)
    return values

def cmd_set_sleep(sleep=1):
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
    id_h = (id>>8) % 256
    id_l = id % 256
    ser.write(construct_command(CMD_DEVICE_ID, [0]*10+[id_l, id_h]))
    read_response()

def aqix25(x):
    pm1 = 0
    pm2 = 12
    pm3 = 35.4
    pm4 = 55.4
    pm5 = 150.4
    pm6 = 250.4
    pm7 = 350.4
    pm8 = 500.4
    aqi1 = 0
    aqi2 = 50
    aqi3 = 100
    aqi4 = 150
    aqi5 = 200
    aqi6 = 300
    aqi7 = 400
    aqi8 = 500
    aqipm25=0
    if x >= pm1 and x <= pm2:
        aqipm25 = ((aqi2 - aqi1) / (pm2 - pm1)) * (x - pm1) + aqi1
    elif x >= pm2 and x <= pm3:
	aqipm25 = ((aqi3 - aqi2) / (pm3 - pm2)) * (x - pm2) + aqi2
    elif x >= pm3 and x <= pm4:
        aqipm25 = ((aqi4 - aqi3) / (pm4 - pm3)) * (x - pm3) + aqi3
    elif pm25 >= pm4 and x <= pm5: 
	aqipm25 = ((aqi5 - aqi4) / (pm5 - pm4)) * (x - pm4) + aqi4
    elif pm25 >= pm5 and x <= pm6:
	aqipm25 = ((aqi6 - aqi5) / (pm6 - pm5)) * (x - pm5) + aqi5
    elif pm25 >= pm6 and x <= pm7: 
	aqipm25 = ((aqi7 - aqi6) / (pm7 - pm6)) * (x - pm6) + aqi6
    elif pm25 >= pm7 and x <= pm8: 
	aqipm25 = ((aqi8 - aqi7) / (pm8 - pm7)) * (x- pm7) + aqi7
    return aqipm25

def aqix10(x):
    pm1 = 0
    pm2 = 54
    pm3 = 154
    pm4 = 254
    pm5 = 354
    pm6 = 424
    pm7 = 504
    pm8 = 604
    aqi1 = 0
    aqi2 = 50
    aqi3 = 100
    aqi4 = 150
    aqi5 = 200
    aqi6 = 300
    aqi7 = 400
    aqi8 = 500
    aqipm10=0
    if x >= pm1 and x <= pm2:
        aqipm10 = ((aqi2 - aqi1) / (pm2 - pm1)) * (x - pm1) + aqi1
    elif x >= pm2 and x <= pm3:
	aqipm10 = ((aqi3 - aqi2) / (pm3 - pm2)) * (x - pm2) + aqi2
    elif x >= pm3 and x <= pm4:
        aqipm10 = ((aqi4 - aqi3) / (pm4 - pm3)) * (x - pm3) + aqi3
    elif pm25 >= pm4 and x <= pm5: 
	aqipm10 = ((aqi5 - aqi4) / (pm5 - pm4)) * (x - pm4) + aqi4
    elif pm25 >= pm5 and x <= pm6:
	aqipm10 = ((aqi6 - aqi5) / (pm6 - pm5)) * (x - pm5) + aqi5
    elif pm25 >= pm6 and x <= pm7: 
	aqipm10 = ((aqi7 - aqi6) / (pm7 - pm6)) * (x - pm6) + aqi6
    elif pm25 >= pm7 and x <= pm8: 
	aqipm10 = ((aqi8 - aqi7) / (pm8 - pm7)) * (x- pm7) + aqi7
    return aqipm10

def aqindex():
    cmd_set_sleep(0)
    cmd_set_mode(1);
    for t in range(3):
        values = cmd_query_data();
        if values is not None:
            try:
                timest = datetime.now() + timedelta(hours=0)
		pm25=values[0]
                aqi_pm25=aqix25(pm25)
		pm10=values[1]
                aqi_pm10=aqix10(pm10)
                humidity, temperature = Adafruit_DHT.read_retry(11, 4)
                #print(str(timest), " PM2.5: ", pm25, ", PM10: ", pm10, "Temperature:", temperature,"Humidity:",humidity)
                time.sleep(2)
            except ValueError:
                print("Value Error Caught")
            except IndexError:
                print("Index Error Caught")
            except :
                print("Error Caught")
    if len(data) > 100:
        data.pop(0)
    print("Last Reading done by ", str(timest))
    # append new values to CSV file
    #data.append({'pm25': values[0], 'pm10': values[1], 'time': time.strftime("%d.%m.%Y %H:%M:%S")})
    #data.append({'pm25': str(pm25), 'pm10': str(pm10), 'time': time.strftime("%d.%m.%Y %H:%M:%S")})
    #pm25=values[0]
    #pm10=values[1]
    file = open('/var/www/html/aqidata.csv','a')
    file.write(str(timest))
    file.write(",")
    file.write(str(pm25))
    file.write(",")
    file.write(str(pm10))
    file.write(",")
    file.write(str(temperature))
    file.write(",")
    file.write(str(humidity))
    file.write("\n")      
    file.close()
    
    # Append values as html markups
    file = open('/var/www/html/aqi.txt','a')
    file.write("<tr><td>")
    file.write(str(timest))
    file.write("</td><td>")
    file.write(str(pm25))
    file.write("</td><td>")
    file.write(str(pm10))
    file.write("</td></tr>")
    file.write(str(temperature))
    file.write("</td></tr>")
    file.write(str(humidity))
    file.write("</td></tr>")
    file.write("\n")        
    file.close()

    # Write in json file
    file = open('/var/www/html/aqi.json','w')
    file.write("{\"entry\": [{\"time\":\"")
    file.write(str(timest))
    file.write("\",\"pm25\":\"")
    file.write(str(pm25))
    file.write("\",\"pm10\":\"")
    file.write(str(pm10))
    file.write("\",\"temperature\":\"")
    file.write(str(temperature))
    file.write("\",\"humidity\":\"")
    file.write(str(humidity))
    file.write("\"}]}")
    file.close()
    
    print("Waiting an hour for next reading...")
    cmd_set_mode(0);
    cmd_set_sleep()

from datetime import datetime, timedelta

while 1:
    aqindex()
    dt2 = datetime.now()
    dt2=dt2.hour
    dt1 = datetime.now() + timedelta(hours=1)
    dt1=dt1.hour
    while dt1 != dt2:
        time.sleep(1)
        dt2 = datetime.now()
        dt2=dt2.hour
        #print(dt2)

        