#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Importing required modules
import argparse
import os
import subprocess
import sys
import time
import threading

# Importing necessary functionalities from ComNetsEmu and Mininet
from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# Function to add streaming container
def add_streaming_container(manager, name, role, image, shared_dir):
    return manager.addContainer(
        name, role, image, '', docker_args={
            'volumes': {
                shared_dir: {'bind': '/home/pcap/', 'mode': 'rw'}
            }
        }
    )

# Function to start server
def start_server():
    subprocess.run(['docker', 'exec', '-it', 'streaming_server', 'bash', '-c', 'cd /home && python3 video_streaming.py'])

# Function to start client
def start_client():
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 get_video_streamed.py'])

# Main execution starts here
if __name__ == '__main__':
    # Setting up command-line argument parsing
    parser = argparse.ArgumentParser(description='video streaming application.')
    parser.add_argument('--autotest', dest='autotest', action='store_const', const=True, default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    args = parser.parse_args()

    # Setting values for bandwidth and delay
    bandwidth = 10  # bandwidth in Mbps
    delay = 5       # delay in milliseconds
    autotest = args.autotest

    # Preparing a shared folder to store the pcap files
    script_directory = os.path.abspath(os.path.dirname(__file__))
    shared_directory = os.path.join(script_directory, 'pcap')

    # Creating the shared directory if it doesn't exist
    if not os.path.exists(shared_directory):
        os.makedirs(shared_directory)

    # Configuring the logging level
    setLogLevel('info')

    # Creating a network with Containernet (a Docker-compatible Mininet fork) and a virtual network function manager
    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    # Adding a controller to the network
    info('*** Add controller\n')
    net.addController('c0')

    # Setting up Docker hosts as network nodes
    info('*** Creating hosts\n')
    server = net.addDockerHost(
        'server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'}
    )
    client = net.addDockerHost(
        'client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'}
    )

    # Adding switches and links to the network
    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')
    net.addLink(switch1, server)
    middle_link = net.addLink(switch1, switch2, bw=bandwidth, delay=f'{delay}ms')
    net.addLink(switch2, client)

    # Starting the network
    info('\n*** Starting network\n')
    net.start()

    # Testing connectivity by pinging server from client
    info("*** Client host pings the server to test for connectivity: \n")
    reply = client.cmd("ping -c 5 10.0.0.1")
    print(reply)

    # Adding containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    # Creating threads to run the server and client
    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)

    # Starting the threads
    server_thread.start()
    client_thread.start()

    # Waiting for the server and client threads to finish
    server_thread.join()
    client_thread.join()

    # If not in autotest mode, start an interactive CLI
    if not autotest:
        CLI(net)

    # Cleanup: removing containers and stopping the network and VNF manager
    mgr.removeContainer('streaming_server')
    mgr.removeContainer('streaming_client')
    net.stop()
    mgr.stop()
