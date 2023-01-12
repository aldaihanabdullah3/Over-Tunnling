# Simple linux tun/tap device example tunnel over udp
# create tap device with ip tuntap add device0 tap
# set ip address on it and run tap-linux on that device and set desitation ip
# run same on another node, changing dst ip to first node

import base64
import curses
import subprocess
import threading
import argparse
import os
import signal
from datetime import datetime, timedelta, timezone
from time import sleep
from tuntap import TunTap

status = 'DISCONNECTED'
bytes_read = 0
bytes_sent = 0
stop_event = threading.Event()

def handle_signal(sig, frame):
    stop_event.set()


def write_file(data: datetime, file_path: str, file_name: str):
    base64_data = base64.b64encode(data).decode('utf-8')
    with open(os.path.join(file_path, file_name), "w") as f:
        f.write(base64_data)


def read_file(file_path: str, file_name: str):
    with open(os.path.join(file_path, file_name), 'r') as file:
        base64_data = file.read().strip()
        data = base64.b64decode(base64_data)
        return data


def list_files_by_date(path: str, date: datetime):
    files = os.listdir(path)
    files = [file for file in files if os.path.isfile(os.path.join(path, file))]
    output_files = [file for file in files if datetime.fromtimestamp(os.path.getctime(os.path.join(path,file))) > date ]
    return output_files


def delete_old_files(path: str, date: datetime):
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            file_date = datetime.fromtimestamp(os.path.getctime(file_path))
            if file_date < date:
                os.remove(file_path)
                print(f"deleting {file_path}")


def writing_thread(path: str, tap: TunTap, stop: threading.Event):
    counter = 0
    global bytes_sent
    while not stop.is_set():
        data = tap.read(1518) #default MTU
        if not data:
            continue
        
        bytes_sent += len(data)
        write_file(data, path, str(counter)+".pp")
        counter += 1
        #delete_old_files(path, datetime.now() - timedelta(seconds=10)) #This causes problems !
        # Do Not Enable deletion of Old Files
    
    print("Joining Writing Thread")


def reading_thread(path: str, tap: TunTap, stop: threading.Event):
    global bytes_read
    ti = datetime.now()
    while not stop.is_set():
        for x in list_files_by_date(path, ti):
            data = read_file(path, x)
            bytes_read += len(data)
            tap.write(data)
            tmp_ti = datetime.fromtimestamp(os.path.getctime(os.path.join(path, x)))
            if tmp_ti > ti:
                ti = tmp_ti
    
    print("Joining Reading Thread")


def ping_thread(target: str, stop: threading.Event):
    global status
    while not stop.is_set():
        try:
            ping = subprocess.run(['ping', '-c', '1', target], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, universal_newlines=True)
            output = ping.stdout
            latency = output.split("time=")[1].split(" ")[0]
            if ping.returncode == 0:
                status = 'CONNECTED, '+str(latency)+'       '
            else:
                status = 'DISCONNECTED          '
        
        except subprocess.TimeoutExpired:
            status = 'DISCONNECTED          '
        except Exception as e:
            status = 'DISCONNECTED          '
        
        sleep(1)


def status_displayer(stdscr, stop: threading.Event):
    curses.curs_set(0)
    while not stop.is_set():
        stdscr.addstr(0, 0, f"Status: {status}")
        stdscr.addstr(1, 0, f"Rx: {bytes_read}")
        stdscr.addstr(2, 0, f"Tx: {bytes_sent}")
        stdscr.refresh()
        sleep(1)


def main(stop):
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--writepath', type=str, required=True)
    parser.add_argument('--readpath', type=str, required=True)
    parser.add_argument('--tap', type=str, required=True)
    parser.add_argument('--tapAddress', type=str, required=True)
    parser.add_argument('--tapTarget', type=str, required=True)
    parser.add_argument('--tapMask', type=str, required=True)
    args = parser.parse_args()

    readpath = args.readpath
    writepath = args.writepath
    nic = args.tap
    target_ip = args.tapTarget
    tap = TunTap(nic_type="Tap", nic_name=nic)
    tap.config(ip=args.tapAddress, mask=args.tapMask)
    
    #clear_file(readfile)
    delete_old_files(writepath, datetime.now()) #clear only write path, read path should be cleared by other end
    thread_read = threading.Thread(target=reading_thread, args=(readpath, tap, stop))
    thread_write = threading.Thread(target=writing_thread, args=(writepath, tap, stop))
    thread_ping = threading.Thread(target=ping_thread, args=(target_ip, stop))
    
    # start the threads
    thread_read.start()
    thread_write.start()
    thread_ping.start()

    curses.wrapper(status_displayer, stop)

    # wait for the threads to finish
    thread_read.join()
    thread_write.join()
    thread_ping.join()
    tap.close()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    main(stop_event)

