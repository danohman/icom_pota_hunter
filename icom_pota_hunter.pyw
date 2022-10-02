import os
import time
import serial
import struct
import json
import re
import socket
import pytz
import PySimpleGUI as sg
import pyperclip
from datetime import datetime
from urllib.request import urlopen

###########################################################################
civaddr = '0x94' # Icom IC-7300 default
comport = 'COM5'
baudrate = 19200
radiotimezone = 'UTC' # Timezone - eg; 'UTC' or 'America/New_York', etc
potalogo = r'C:\Users\Dan\Dropbox\Radio Things\POTA\icom_pota_hunter\pota-logo.png'
###########################################################################

# global vars
lateshifthours = ['00','01','02','03','04','05','06','07','08','09','10','11']
spots = []
hunted = []
current_spot_num = 0
current_spot_frequency = ''
current_spot_activator = ''
current_spot_parknumber = ''
current_spot_parkinfo = ''
current_spot_spotid = ''

ser = serial.Serial(comport, baudrate)
ser.setDTR(False)
ser.setRTS(False)

def send_to_radio(arr):
    c = 0
    while (c < len(arr)):
        senddata = int(bytes(arr[c], 'UTF-8'), 16)
        ser.write(struct.pack('>B', senddata))
        c += 1

def set_clock():
    hours = datetime.now(pytz.timezone(radiotimezone)).strftime("%H")
    hours = str(hours)
    minutes = datetime.now(pytz.timezone(radiotimezone)).strftime("%M")
    minutes = str(minutes)
    window['-INFO-'].update('Radio clock has been set to ' + hours + ':' + minutes)
    window.refresh()
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
    
    return modename

def get_spots():
    window['-INFO-'].update('Fetching current POTA spots...')
    window.refresh()
    time.sleep(1)
    url = "https://api.pota.app/spot/activator"
    response = urlopen(url)
    spotdata = sorted(json.loads(response.read()), key=lambda k: k['frequency'], reverse=False)
    
    for spot in spotdata:
        if spot['mode'] == 'SSB' and not re.search('qrt|qsy', spot['comments'], re.IGNORECASE):
        #if spot['mode']:
                
            spottime = datetime.strptime(spot['spotTime'], '%Y-%m-%dT%H:%M:%S')
            nowtime = datetime.utcnow()

            spotage_mins = int((nowtime - spottime).total_seconds() / 60)
            spotage_secs = int((nowtime - spottime).total_seconds())
                                
            if spotage_mins >= 1:
                spotage = str(spotage_mins) + ' min ago'
            else:
                spotage = str(spotage_secs) + ' sec ago'
                        
            parklocations = spot['locationDesc'].split(',')
            if len(parklocations) > 2:
                parklocation = parklocations[0] + ',' + parklocations[1] + ',+' + str(len(parklocations)-2)
            else:
                parklocation = parklocations[0]
 
            spots.append(
                [
                    spot['frequency'],
                    spot['activator'],
                    spot['reference'],
                    spot['name'],
                    parklocation,
                    spot['count'],
                    spotage,
                    spot['spotter'],
                    spot['comments']
                ]
            )

    if len(spots) == 0:
        window['-INFO-'].update('No non-QRT SSB spots found')
        window.refresh()
        window['click_copy_freq'].update(visible=False)
        window['click_copy_activator'].update(visible=False)
        window['click_copy_parknumber'].update(visible=False)
        window['click_copy_parkinfo'].update(visible=False)
        window['click_mark_hunted'].update(visible=False)

    else:
        window['-INFO-'].update('Found ' + str(len(spots)) + ' spots! Click "Next Spot" to tune VFO')
        window.refresh()
        time.sleep(1)

    return spots
   
def update_info_window(arr):
    global current_spot_frequency
    global current_spot_activator
    global current_spot_parknumber
    global current_spot_parkinfo
    global current_spot_spotid

    lastspotcomment = arr[6] + ' > ' + arr[7] + ' > ' + arr[8]
    window['-SPOTFREQ-'].update(arr[0])
    window['-SPOTACTIVATOR-'].update(arr[1])
    window['-SPOTPARKNUMBER-'].update(arr[2])
    window['-SPOTPARKINFO-'].update('(' + arr[4] + ') ' + arr[3])
    window['-SPOTCOUNT-'].update(arr[5])
    window['-SPOTLAST-'].update(lastspotcomment)

    current_spot_frequency = arr[0]
    current_spot_activator = arr[1]
    current_spot_parknumber = 'POTA ' + arr[2]
    current_spot_parkinfo = '(' + arr[4] + ') ' + arr[3]
    
    window['click_copy_freq'].update(visible=True)
    window['click_copy_activator'].update(visible=True)
    window['click_copy_parknumber'].update(visible=True)
    window['click_copy_parkinfo'].update(visible=True)
    
    if current_spot_frequency + ':' + current_spot_activator in hunted:
        window['click_mark_hunted'].update(visible=False)
        window['spotid_hunted'].update(visible=True)
    else:
        window['click_mark_hunted'].update(visible=True)
        window['spotid_hunted'].update(visible=False)

def tune_next_spot():
        global current_spot_num
        
        if len(spots) == 0:
            window['-INFO-'].update('No spots found! Click "Get Spots"')
            window.refresh()
        else:
            update_info_window(spots[current_spot_num])
            modename = set_vfo_mode_and_frequency(spots[current_spot_num][0])

            display_spot_num = current_spot_num + 1                                 

            window['-INFO-'].update('Spot ' + str(display_spot_num) + ' of ' + str(len(spots)) + ' : VFO tuned to ' + spots[current_spot_num][0] + ' ' + modename)
            window.refresh()

            if current_spot_num == len(spots) - 1:
                current_spot_num = 0
            else:
                current_spot_num += 1

def tune_previous_spot():
        global current_spot_num
        
        if len(spots) == 0:
            window['-INFO-'].update('No spots found! Click "Get Spots"')
            window.refresh()
        else:

            if current_spot_num == 0:
                current_spot_num =  len(spots) - 1
            else:
                current_spot_num -= 1

            update_info_window(spots[current_spot_num])
            modename = set_vfo_mode_and_frequency(spots[current_spot_num][0])

            display_spot_num = current_spot_num + 1                                 

            window['-INFO-'].update('Spot ' + str(display_spot_num) + ' of ' + str(len(spots)) + ' : VFO tuned to ' + spots[current_spot_num][0] + ' ' + modename)
            window.refresh()
 
def update_late_shift_text():
    hour = datetime.now(pytz.timezone('UTC')).strftime("%H")    
    if hour in lateshifthours:
        window['lateshift'].update(visible=True)

##########################################################

sg.ChangeLookAndFeel('DarkGreen6')

col1 = sg.Col(
    [
        [
            sg.Text('Frequency', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.pin(sg.Button(' Copy ', key='click_copy_freq', visible=False)),
            sg.Text('None', key='-SPOTFREQ-', font=("Helvetica", 12)),
            sg.pin(sg.Button(' Mark Hunted ', key='click_mark_hunted', button_color=('white','darkgreen'), visible=False)),          
            sg.Text(' (Hunted Spot) ', key='spotid_hunted', visible=False, text_color='darkred', font=("Helvetica", 12, 'bold'))
        ],
        [
            sg.Text('Activator', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.pin(sg.Button(' Copy ', key='click_copy_activator', visible=False)),
            sg.Text('None', key='-SPOTACTIVATOR-', font=("Helvetica", 12))
        ],
        [
            sg.Text('Park Number', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.pin(sg.Button(' Copy ', key='click_copy_parknumber', visible=False)),
            sg.Text('None', key='-SPOTPARKNUMBER-', font=("Helvetica", 12))
        ],
        [
            sg.Text('Park Info', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.pin(sg.Button(' Copy ', key='click_copy_parkinfo', visible=False)),
            sg.Text('None', key='-SPOTPARKINFO-', font=("Helvetica", 12))
        ],
        [
            sg.Text('Spot Count', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.Text('None', key='-SPOTCOUNT-', font=("Helvetica", 12))
        ],
        [
            sg.Text('Last Spot', font=("Helvetica", 12, 'bold'), size=(10,1)),
            sg.Text('None', key='-SPOTLAST-', font=("Helvetica", 12))
        ]
    ], size=(900,190), pad=(0,0),    
)

col2 = sg.Col(
    [
        [
            sg.Button(' Get Spots ', key='click_get_spots', button_color=('white','darkgreen'), tooltip='Fetch current spots'),
            sg.Button(' Previous Spot ', key='click_previous_spot', button_color=('white','darkgreen'), tooltip='Tune VFO to Previous Spot'),
            sg.Button(' Next Spot ', key='click_next_spot', button_color=('white','darkgreen'), tooltip='Tune VFO to Next Spot'),          
            sg.Button(' Sync Clock ', key='click_sync_clock', button_color=('white','darkgreen'), tooltip='Sync radio time'),
            sg.Button(' About ', key='click_about', button_color=('white','darkgreen')),
            sg.Button(' Exit ', key='click_exit', button_color=('white','darkred')),
            sg.Text('Click "Get Spots" to start', key='-INFO-', justification="center", text_color='blue', font=("Helvetica", 11, 'bold'), pad=(40,0), size=(40,1), relief=sg.RELIEF_SUNKEN)
        ]
    ], size=(900,40), pad=(0,0),
)

col3 = sg.Col(
    [
        [
            sg.Image(potalogo),
            sg.Text('WD4DAN ICOM POTA Hunter', justification="center", font=("Helvetica", 18))
        ]
    ], size=(900,200), pad=(0,0),
)

col4 = sg.Col(
    [
        [
            sg.Multiline(size=(40,6), key='-notes-', font=("Helvetica", 12, 'bold'))
        ],
        [
            sg.Button(' Copy ', key='click_copy_notes'),
            sg.Button(' Clear ', key='click_clear_notes')          
        ]
    ], size=(400,160), pad=(0,0),
)

col5 = sg.Col(
    [
        [
            sg.Text('LATE SHIFT', visible=False, key='lateshift', justification="left", text_color='cyan', font=("Helvetica", 16, 'bold'), pad=(0,0), size=(20,1))
        ],
    ], size=(400,160), pad=(0,0),
)

layout = [
    [sg.Frame('', [[col3]], border_width=0)],
    [
        sg.Frame(' Quick Notes ', [[col4]]),
        sg.Frame('', [[col5]], border_width=0)
    ],
    [sg.Frame(' Spot Information ', [[col1]])],
    [sg.Frame(' Commands and Information ', [[col2]])]
]

window = sg.Window('WD4DAN ICOM POTA Hunter', layout, finalize=True)
update_late_shift_text()

while True:
    event, values = window.Read()

    update_late_shift_text()
    
    if event == sg.WIN_CLOSED or event == 'click_exit':
        break

    if event == 'click_mark_hunted':
        hunted.append(current_spot_frequency + ':' + current_spot_activator)
        window['click_mark_hunted'].update(visible=False)
        window['spotid_hunted'].update(visible=True)
        
    if event == 'click_copy_freq':
        pyperclip.copy(current_spot_frequency)
        
    if event == 'click_copy_activator':
        pyperclip.copy(current_spot_activator)

    if event == 'click_copy_parknumber':
        pyperclip.copy(current_spot_parknumber)

    if event == 'click_copy_parkinfo':
        pyperclip.copy(current_spot_parkinfo)
        
    if event == 'click_copy_notes':
        pyperclip.copy(values['-notes-'])

    if event == 'click_clear_notes':
        window['-notes-'].update('')
        
    if event == 'click_about':
        sg.popup('Version 1.0','Dan Muntz - WD4DAN', 'dan@wd4dan.net', '', 'Spots shown are "SSB" spots that are not "QRT" or "QSY"', '')

    if event == 'click_sync_clock':
        set_clock()
        
    if event == 'click_get_spots':
        spots = []
        spots = get_spots()
        current_spot_num = 0
        tune_next_spot()
        
    if event == "click_next_spot":
        tune_next_spot()
        
    if event == "click_previous_spot":
        tune_previous_spot()
        

window.close()
