#########################################################################
# Dan Muntz - WD4DAN               Sept 2022
# dan@wd4dan.net
#
# If you use this, all I ask is you shoot me an email and let me know!
#
# You'll need the following modules installed:
#       pytz == 'pip install pytz'
#       PySimpleGUI == 'pip install PySimpleGUI'
#########################################################################

import os
import time
import serial
import struct
from time import sleep
from datetime import datetime
from urllib.request import urlopen
import json
import re
import socket
import pytz
import PySimpleGUI as gui

civaddr = '0x94' # Icom IC-7300 default
comport = 'COM5'
baudrate = 19200
radiotimezone = 'UTC' # Timezone - eg; 'UTC' or 'America/New_York', etc

ser = serial.Serial(comport, baudrate)
ser.setDTR(False)
ser.setRTS(False)

def send_to_radio(arr):
    c = 0
    while (c < len(arr)):
        senddata = int(bytes(arr[c], 'UTF-8'), 16)
        ser.write(struct.pack('>B', senddata))
        c += 1

# Set radio clock time specified timezone - Sync time with PC
def set_clock():
    hours = datetime.now(pytz.timezone(radiotimezone)).strftime("%H")
    hours = str(hours)
    minutes = datetime.now(pytz.timezone(radiotimezone)).strftime("%M")
    minutes = str(minutes)
    print('\nSet radio clock to ' + hours + ':' + minutes)
    hours = "0x" + hours
    minutes = "0x" + minutes
    send_to_radio(['0xfe','0xfe', civaddr, '0xe0', '0x1a', '0x05', '0x00', '0x95', hours, minutes, '0xfd'])

def itobcd(i):
    i = i.zfill(9)
    out =  r'\x'+i[8]+'0'+r'\x'+i[6]+i[7]+r'\x'+i[4]+i[5]+r'\x'+i[2]+i[3]+r'\x'+i[0]+i[1]
    return out.split("\\x")

def set_vfo_mode_and_frequency(freq):
    origfreq = freq
    freq = freq.replace('.', '')
    
    if freq[0] == '3' or freq[0] == '7':
        # only pad 6 for these bands
        freq = freq.ljust(6, '0')
    else:
        freq = freq.ljust(7, '0')
        
    hexfreq = itobcd(freq)
    f4 = '0x'+hexfreq[4]
    f3 = '0x'+hexfreq[3]
    f2 = '0x'+hexfreq[2]
    f1 = '0x'+hexfreq[1]
    
    send_to_radio(['0xfe','0xfe', civaddr, '0xe0', '0x00', f1, f2, f3, f4, '0x00', '0xfd'])       
                          
    # figure out what mode - if freq is less than 10 MHz, we'll assume LSB
    if int(float(origfreq)) < 10000:
        mode = '0x00'
        modename = 'LSB'
    else:
        mode = '0x01'
        modename = 'USB'

    # send vfo mode to radio
    ## start, start, civaddr, pcaddr, writemode, mode, filterwidth, execute
    send_to_radio(['0xfe','0xfe', civaddr, '0xe0', '0x06', mode, '0x02', '0xfd'])
                          
    # send to UDP for pickup by logger
    # udpport = 2251
    # udphost = '127.0.0.1'
    # udpmsg = 'bleh'
    # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
    # sock.sendto(udpmsg.encode(), (udphost, udpport))
  
def run_spots():
    print("\nFetching current POTA spots...")
    url = "https://api.pota.app/spot/activator"
    response = urlopen(url)
    spotdata = sorted(json.loads(response.read()), key=lambda k: k['frequency'], reverse=False)
    numspots = 0

    for spot in spotdata:
        if spot['mode'] == 'SSB' and not re.search('qrt', spot['comments'], re.IGNORECASE):
            numspots += 1
                
            spottime = datetime.strptime(spot['spotTime'], '%Y-%m-%dT%H:%M:%S')
            nowtime = datetime.utcnow()

            spotage_mins = int((nowtime - spottime).total_seconds() / 60)
            spotage_secs = int((nowtime - spottime).total_seconds())
                                
            if spotage_mins >= 1:
                spotage = str(spotage_mins) + ' min ago'
            else:
                spotage = str(spotage_secs) + ' sec ago' 
                    
            print('\n')
            print('Frequency... ' + spot['frequency'])
            print('Activator... ' + spot['activator'])
            print('Park Info... POTA ' + spot['reference'] + ' (' + spot['name'] + ') [' + spot['locationDesc'] + ']')
            print('Num Spots... ' + str(spot['count']))
            print('Last Spot... ' + spotage + ' -> ' + spot['spotter'] +' -> ' + spot['comments'] + '\n')

            set_vfo_mode_and_frequency(spot['frequency'])
               
            input('Press ENTER to move to next spot...')
            
    print("\nDone! " + str(numspots) + " spots found\n")
    input("Press ENTER to run spots again, or close window to quit...")
    print('\n')
    run_spots()

# Set radio clock if you wanna
#set_clock()

run_spots()
