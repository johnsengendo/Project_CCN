#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import sys

from comnetsemu.cli import CLI
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

def main():
    parser = argparse.ArgumentParser(description='Script for running the video streaming app.')
    parser.add_argument('--link-bw', metavar='link_bw', type=float, nargs='?', default=10,
                        help='initial bandwidth of the link connecting the two switches in the topology (the bandwidth '
                             'is defined in Mbit/s).')
    parser.add_argument('--link-delay', metavar='link_delay', type=float, nargs='?', default=10,
                        help='initial delay of the link connecting the two switches in the topology (the delay is '
                             'defined in ms).')
    args = parser.parse_args()

    # Read the command-line arguments
    bandwidth = max(args.link_bw, 0.000001)
    delay = max(args.link_delay, 0)

    # Create the directory that will be shared with the services docker containers
    script_dir = os.path.abspath(os.path.join('./', os.path.dirname(sys.argv[0])))
    shared_dir = os.path.join(script_dir, 'shared')
    os.makedirs(shared_dir, exist_ok=True)

    # Set the logging level
    setLogLevel('info')

    # Instantiate the network and the VNF manager objects
    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    # Add the controller to the network
    info('*** Add controller\n')
    net.addController('c0')

    # Add the hosts (server and client) to the network
    info('*** Creating hosts\n')
    server = net.addDockerHost(
        'server', dimage='video_streaming_server', ip='10.0.0.1', docker_args={'hostname': 'server'}
    )
    client = net.addDockerHost(
        'client', dimage='video_streaming_client', ip='10.0.0.2', docker_args={'hostname': 'client'}
    )

    # Add switches and links to the network
    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')
    net.addLink(switch1, server)
    middle_link = net.addLink(switch1, switch2, bw=bandwidth, delay=f'{delay}ms')
    net.addLink(switch2, client)

    # Start the network
    info('\n*** Starting network\n')
    net.start()
    print()

    # Add the video streaming (server and client) services
    info('*** Adding Docker containers\n')
    try:
        streaming_server = mgr.addContainer(
            'streaming_server', 'server', 'video_streaming_server', '', docker_args={
                'volumes': {
                    shared_dir: {'bind': '/home/shared/', 'mode': 'rw'}
                }
            }
        )
        info('*** Added streaming_server container\n')
    except Exception as e:
        info(f'Error adding streaming_server container: {e}')
        
    try:
        streaming_client = mgr.addContainer(
            'streaming_client', 'client', 'video_streaming_client', '', docker_args={
                'volumes': {
                    shared_dir: {'bind': '/home/shared/', 'mode': 'rw'}
                }
            }
        )
        info('*** Added streaming_client container\n')
    except Exception as e:
        info(f'Error adding streaming_client container: {e}')

    # Ensure Docker containers are running
    info('*** Starting Docker containers\n')
    try:
        subprocess.run('docker start streaming_server', check=True, shell=True)
        info('*** Started streaming_server container\n')
    except subprocess.CalledProcessError as e:
        info(f'Error starting streaming_server container: {e}')

    try:
        subprocess.run('docker start streaming_client', check=True, shell=True)
        info('*** Started streaming_client container\n')
    except subprocess.CalledProcessError as e:
        info(f'Error starting streaming_client container: {e}')

    # Perform the video streaming and packet capture
    info('*** Starting video streaming and packet capture\n')
    try:
        subprocess.run('docker exec -d streaming_server /home/stream_video.sh', check=True, shell=True)
        info('*** Started video streaming on streaming_server\n')
    except subprocess.CalledProcessError as e:
        info(f'Error starting video streaming on streaming_server: {e}')

    try:
        subprocess.run('docker exec -d streaming_client /home/get_video_stream.sh', check=True, shell=True)
        info('*** Started packet capture on streaming_client\n')
    except subprocess.CalledProcessError as e:
        info(f'Error starting packet capture on streaming_client: {e}')

    # Wait for the user to stop the program
    input("Press Enter to stop the video streaming and packet capture...")

    # Stop the video streaming and packet capture
    info('*** Stopping video streaming and packet capture\n')
    try:
        subprocess.run('docker exec streaming_server pkill -f stream_video.sh', check=True, shell=True)
        info('*** Stopped video streaming on streaming_server\n')
    except subprocess.CalledProcessError as e:
        info(f'Error stopping video streaming on streaming_server: {e}')

    try:
        subprocess.run('docker exec streaming_client pkill -f get_video_stream.sh', check=True, shell=True)
        info('*** Stopped packet capture on streaming_client\n')
    except subprocess.CalledProcessError as e:
        info(f'Error stopping packet capture on streaming_client: {e}')

    # Perform the closing operations
    info('*** Stopping Docker containers and network\n')
    try:
        mgr.removeContainer('streaming_server')
        info('*** Removed streaming_server container\n')
    except Exception as e:
        info(f'Error removing streaming_server container: {e}')

    try:
        mgr.removeContainer('streaming_client')
        info('*** Removed streaming_client container\n')
    except Exception as e:
        info(f'Error removing streaming_client container: {e}')
    
    net.stop()
    mgr.stop()
    info('*** Network stopped\n')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)