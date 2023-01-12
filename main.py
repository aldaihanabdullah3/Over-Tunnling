# Simple linux tun/tap device example tunnel over udp
# create tap device with ip tuntap add device0 tap
# set ip address on it and run tap-linux on that device and set desitation ip
# run same on another node, changing dst ip to first node

import base64
import socket
import threading
import argparse
import os
from datetime import datetime, timedelta
from tuntap import TunTap

EXIT = False

def client2(s, tap, EXIT):
    while not EXIT:
        data = s.recv(2048)
        if not data:
            if EXIT:
                break
            continue
        print("received {} bytes",len(data))
        tap.write(data)


def client(addr, port, tap, EXIT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((addr, port))
        t = threading.Thread(target=client2, args=(s, tap, EXIT))
        t.start()
        while not EXIT:
            data = tap.read(2048)
            if not data:
                if EXIT:
                    break
                continue
            print("writing {} bytes",len(data))
            s.sendall(data)


def server2(conn, tap, EXIT):
    while not EXIT:
        data = tap.read(2048)
        if not data:
            if EXIT:
                break
            continue
        print("writing {} bytes",len(data))
        conn.sendall(data)
    

def server(addr, port, tap, EXIT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((addr, port))
        s.listen()
        conn, client = s.accept()
        with conn:
            print(f"Connected by {client}")
            t = threading.Thread(target=server2, args=(conn, tap, EXIT))
            t.start()
            while True:
                data = conn.recv(1024)
                if not data:
                    if EXIT:
                        break
                    continue
                print("received {} bytes",len(data))
                tap.write(data)


def main_tcp():
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', action='store_true')
    parser.add_argument('--client', action='store_true')
    parser.add_argument('--address', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--tap', type=str, required=True)
    parser.add_argument('--tapAddress', type=str, required=True)
    parser.add_argument('--tapMask', type=str, required=True)
    args = parser.parse_args()

    tap = TunTap(nic_type="Tap", nic_name=args.tap)
    tap.config(ip=args.tapAddress,mask=args.tapMask)

    if args.server:
        server(args.address, args.port, tap, EXIT)
    elif args.client:
        client(args.address, args.port, tap, EXIT)
    else:
        print('Error: Must specify either --server or --client')


def write_file(data, file_path, file_name):
    base64_data = base64.b64encode(data).decode('utf-8')
    with open(os.path.join(file_path, file_name), "w") as f:
        f.write(base64_data)


def writing_th(path, tap, EXIT):
    counter = 0
    while not EXIT:
        data = tap.read(1518) #default MTU
        if not data:
            if EXIT:
                break
            continue
        print("writing",len(data)," bytes")
        write_file(data, path, str(counter)+".pp")
        counter += 1
        delete_old_files(path, datetime.utcnow() - timedelta(seconds=10))


def read_file(file_path, file_name):
    with open(os.path.join(file_path, file_name), 'r') as file:
        base64_data = file.read().strip()
        data = base64.b64decode(base64_data)
        return data
    

def reading_th(path, tap, EXIT):
    ti = datetime.utcnow()
    while not EXIT:
        for x in list_files_by_date(path, ti):
            data = read_file(path, x)
            print("received",len(data)," bytes")
            tap.write(data)
            tmp_ti = datetime.fromtimestamp(os.path.getctime(os.path.join(path, x)))
            if tmp_ti > ti:
                ti = tmp_ti


def list_files_by_date(path, date):
    files = os.listdir(path)
    files = [file for file in files if os.path.isfile(os.path.join(path, file))]
    output_files = [file for file in files if datetime.fromtimestamp(os.path.getctime(os.path.join(path,file))) > date ]
    return output_files


def delete_old_files(path, date):
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            if datetime.fromtimestamp(os.path.getctime(file_path)) < date:
                os.remove(file_path)


def main_files():
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--writepath', type=str, required=True)
    parser.add_argument('--readpath', type=str, required=True)
    parser.add_argument('--tap', type=str, required=True)
    parser.add_argument('--tapAddress', type=str, required=True)
    parser.add_argument('--tapMask', type=str, required=True)
    args = parser.parse_args()

    tap = TunTap(nic_type="Tap", nic_name=args.tap)
    tap.config(ip=args.tapAddress, mask=args.tapMask)
    readpath = args.readpath
    writepath = args.writepath
    
    #clear_file(readfile)
    delete_old_files(writepath, datetime.utcnow()) #clear only write path, read path should be cleared by other end
    thread_read = threading.Thread(target=reading_th, args=(readpath, tap, EXIT))
    thread_write = threading.Thread(target=writing_th, args=(writepath, tap, EXIT))
    
    # start the threads
    thread_read.start()
    thread_write.start()
    
    # wait for the threads to finish
    thread_read.join()
    thread_write.join()


if __name__ == "__main__":
    try:
        #main_tcp()
        main_files()

    except KeyboardInterrupt:
        print("Terminating ...")
        EXIT = True
        exit()
