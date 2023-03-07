#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os

from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

from python_modules.Open5GS import Open5GS

import json, time, yaml

if __name__ == "__main__":

    AUTOTEST_MODE = os.environ.get("COMNETSEMU_AUTOTEST_MODE", 0)

    setLogLevel("info")

    prj_folder = "/home/vagrant/comnetsemu/app/comnetsemu_5Gnet"
    mongodb_folder = "/home/vagrant/mongodbdata"

    env = dict()

    net = Containernet(controller=Controller, link=TCLink)

    slices = {}  # key will be the sst-1, fields: dnn, bw, ip, subnet
    n_slices = input('enter number of slices: ')
    ip = 112
    subnet = 45
    for i in range(int(n_slices)):  # repeats n_slices times, not n-1
        dnn = input('enter dnn for slice ' + str(i + 1) + ': ')
        bw = input('enter bandwidth (Mbps) for slice ' + str(i + 1) + ': ')
        slices[i] = {
            'dnn': dnn,
            'bw': bw,
            'ip': '192.168.0.' + str(ip),
            'subnet': '10.' + str(subnet) + '.0.1'
        }
        ip += 1
        subnet += 1

    # edit configuration files
    info("*** Editing configuration files\n")

    # edit smf.yaml (clear fixed)
    with open('./open5gs/config/smf.yaml', 'r') as read_file:
        contents = yaml.safe_load(read_file)
        contents['smf']['subnet'].clear()
        contents['smf']['subnet'].extend([None] * int(n_slices))
        contents['upf']['pfcp'].clear()
        contents['upf']['pfcp'].extend([None] * int(n_slices))
        for i in range(int(n_slices)):
            contents['smf']['subnet'][i] = {
                'addr': slices[i]['subnet'] + '/16',
                'dnn': slices[i]['dnn']
            }
            contents['upf']['pfcp'][i] = {
                'addr': slices[i]['ip'],
                'dnn': slices[i]['dnn']
            }
    # fix output file
    with open('./open5gs/config/smf.yaml', 'w') as dump_file:
        yaml.dump(contents, dump_file)

    # edit nssf.yaml (clear fixed)
    with open('./open5gs/config/nssf.yaml', 'r') as read_file:
        contents = yaml.safe_load(read_file)
        contents['nssf']['nsi'].clear()
        contents['nssf']['nsi'].extend([None] * int(n_slices))
        for i in range(int(n_slices)):
            contents['nssf']['nsi'][i] = {
                'addr': '127.0.0.10',
                'port': 7777,
                's_nssai': {'sst': i + 1, 'sd': 1}
            }
    # fix output file
    with open('./open5gs/config/nssf.yaml', 'w') as dump_file:
        yaml.dump(contents, dump_file)

    # edit amf.yaml (clear fixed)
    with open('./open5gs/config/amf.yaml', 'r') as read_file:
        contents = yaml.safe_load(read_file)
        contents['amf']['guami'][0]['plmn_id'] = {'mcc': '001', 'mnc': '01'}
        contents['amf']['tai'][0]['plmn_id'] = {'mcc': '001', 'mnc': '01'}
        contents['amf']['plmn_support'][0]['plmn_id'] = {'mcc': '001', 'mnc': '01'}
        contents['amf']['plmn_support'][0]['s_nssai'].clear()
        contents['amf']['plmn_support'][0]['s_nssai'].extend([None] * int(n_slices))
        for i in range(int(n_slices)):
            contents['amf']['plmn_support'][0]['s_nssai'][i] = {'sst': i + 1, 'sd': 1}
    # fix output file
    with open('./open5gs/config/amf.yaml', 'w') as dump_file:
        yaml.dump(contents, dump_file)

    # edit open5gs-ue.yaml (clear fixed)
    with open('./ueransim/config/open5gs-ue.yaml', 'r') as read_file:
        contents = yaml.safe_load(read_file)
        contents['sessions'].clear()
        contents['sessions'].extend([None] * int(n_slices))
        contents['configured-nssai'].clear()
        contents['configured-nssai'].extend([None] * int(n_slices))
        for i in range(int(n_slices)):
            contents['sessions'][i] = {
                'type': 'IPv4',
                'slice': {'sst': i + 1, 'sd': 1},
                'emergency': False
            }
            contents['configured-nssai'][i] = {
                'sst': i + 1,
                'sd': 1
            }
    # fix output file
    with open('./ueransim/config/open5gs-ue.yaml', 'w') as dump_file:
        yaml.dump(contents, dump_file)

    # edit open5gs-gnb.yaml (clear fixed)
    with open('./ueransim/config/open5gs-gnb.yaml', 'r') as read_file:
        contents = yaml.safe_load(read_file)
        contents['slices'].clear()
        contents['slices'].extend([None] * int(n_slices))
        for i in range(int(n_slices)):
            contents['slices'][i] = {'sst': i + 1, 'sd': 1}
    # fix output file
    with open('./ueransim/config/open5gs-gnb.yaml', 'w') as dump_file:
        yaml.dump(contents, dump_file)

    # create yaml config files for each upf
    for i in range(int(n_slices)):
        with open('./open5gs/config/default_yaml/upf.yaml', 'r') as read_file:
            contents = yaml.safe_load(read_file)
            contents['logger'] = {'file': '/open5gs/install/var/log/open5gs/upf_' + slices[i]['dnn'] + '.log'}
            contents['upf'] = {
                'pfcp': [{'addr': slices[i]['ip']}],
                'gtpu': [{'addr': slices[i]['ip']}],
                'subnet': [
                    {'addr': slices[i]['subnet'] + '/16',
                     'dnn': slices[i]['dnn'],
                     'dev': 'ogstun'}
                ]
            }
        # fix output file into correct folder
        with open('./open5gs/config/upf_' + slices[i]['dnn'] + '.yaml', 'w') as dump_file:
            yaml.dump(contents, dump_file)

    info("*** Add controller\n")
    net.addController("c0")

    info("*** Adding switch\n")
    s1 = net.addSwitch("s1")
    s2 = net.addSwitch("s2")
    s3 = net.addSwitch("s3")

    info("*** Adding links\n")
    net.addLink(s1, s2, bw=1000, delay="10ms", intfName1="s1-s2", intfName2="s2-s1")
    net.addLink(s2, s3, bw=1000, delay="50ms", intfName1="s2-s3", intfName2="s3-s2")

    info("*** Adding Host for open5gs CP\n")
    cp = net.addDockerHost(
        "cp",
        dimage="my5gc_v2-4-4",
        ip="192.168.0.111/24",
        # dcmd="",
        dcmd="bash /open5gs/install/etc/open5gs/5gc_cp_init.sh",
        docker_args={
            "ports": {"3000/tcp": 3000},
            "volumes": {
                prj_folder + "/log": {
                    "bind": "/open5gs/install/var/log/open5gs",
                    "mode": "rw",
                },
                mongodb_folder: {
                    "bind": "/var/lib/mongodb",
                    "mode": "rw",
                },
                prj_folder + "/open5gs/config": {
                    "bind": "/open5gs/install/etc/open5gs",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
            },
        },
    )

    for i in range(int(n_slices)):
        info("*** Adding Host for open5gs UPF " + slices[i]['dnn'] + "\n")
        env["COMPONENT_NAME"] = "upf_" + slices[i]['dnn']
        env["SUBNET"] = slices[i]['subnet']
        host = net.addDockerHost(
            "upf_" + slices[i]['dnn'],
            dimage="my5gc_v2-4-4",
            ip=slices[i]['ip'] + "/24",
            # dcmd="",
            dcmd="bash /open5gs/install/etc/open5gs/temp/5gc_up_init.sh",
            docker_args={
                "environment": env,
                "volumes": {
                    prj_folder + "/log": {
                        "bind": "/open5gs/install/var/log/open5gs",
                        "mode": "rw",
                    },
                    prj_folder + "/open5gs/config": {
                        "bind": "/open5gs/install/etc/open5gs/temp",
                        "mode": "rw",
                    },
                    "/etc/timezone": {
                        "bind": "/etc/timezone",
                        "mode": "ro",
                    },
                    "/etc/localtime": {
                        "bind": "/etc/localtime",
                        "mode": "ro",
                    },
                },
                "cap_add": ["NET_ADMIN"],
                "sysctls": {"net.ipv4.ip_forward": 1},
                "devices": "/dev/net/tun:/dev/net/tun:rwm"
            },
        )
        net.addLink(host, s2, bw=1000, delay="1ms", intfName1="upf_" + slices[i]['dnn'] + "-s2",
                    intfName2="s2-upf_" + slices[i]['dnn'])

    info("*** Adding gNB\n")
    env["COMPONENT_NAME"] = "gnb"
    gnb = net.addDockerHost(
        "gnb",
        dimage="myueransim_v3-2-6",
        ip="192.168.0.131/24",
        # dcmd="",
        dcmd="bash /mnt/ueransim/open5gs_gnb_init.sh",
        docker_args={
            "environment": env,
            "volumes": {
                prj_folder + "/ueransim/config": {
                    "bind": "/mnt/ueransim",
                    "mode": "rw",
                },
                prj_folder + "/log": {
                    "bind": "/mnt/log",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
                "/dev": {"bind": "/dev", "mode": "rw"},
            },
            "cap_add": ["NET_ADMIN"],
            "devices": "/dev/net/tun:/dev/net/tun:rwm"
        },
    )

    info("*** Adding UE\n")
    env["COMPONENT_NAME"] = "ue"
    ue = net.addDockerHost(
        "ue",
        dimage="myueransim_v3-2-6",
        ip="192.168.0.132/24",
        # dcmd="",
        dcmd="bash /mnt/ueransim/open5gs_ue_init.sh",
        docker_args={
            "environment": env,
            "volumes": {
                prj_folder + "/ueransim/config": {
                    "bind": "/mnt/ueransim",
                    "mode": "rw",
                },
                prj_folder + "/log": {
                    "bind": "/mnt/log",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
                "/dev": {"bind": "/dev", "mode": "rw"},
            },
            "cap_add": ["NET_ADMIN"],
            "devices": "/dev/net/tun:/dev/net/tun:rwm"
        },
    )

    net.addLink(cp, s3, bw=1000, delay="1ms", intfName1="cp-s1", intfName2="s1-cp")
    net.addLink(ue, s1, bw=1000, delay="1ms", intfName1="ue-s1", intfName2="s1-ue")
    net.addLink(gnb, s1, bw=1000, delay="1ms", intfName1="gnb-s1", intfName2="s1-gnb")

    print(f"*** Open5GS: Init subscriber for UE 0")

    with open('python_modules/subscriber_profile.json', 'r') as file:
        data = json.load(file)
    default = True
    data['slice'].clear()
    data['slice'].extend([None] * int(n_slices))
    for i in range(int(n_slices)):
        if i != 0:
            default = None
        data['slice'][i] = {
            'sst': i + 1,
            'default_indicator': default,
            'sd': '000001',
            'session': [{
                'name': slices[i]['dnn'],
                'type': 3,
                'pcc_rule': [],
                'ambr': {
                    'Comment': 'unit=2 ==> Mbps',
                    'uplink': {'value': int(slices[i]['bw']), 'unit': 2},
                    'downlink': {'value': int(slices[i]['bw']), 'unit': 2}
                },
                'qos': {
                    'index': 8,
                    'arp': {
                        'priority_level': 15,
                        'pre_emption_capability': 1,
                        'pre_emption_vulnerability': 1
                    }
                }
            }]
        }
    # Write the updated data back to the JSON file
    with open('python_modules/subscriber_profile3.json', 'w') as file:
        json.dump(data, file)

    o5gs = Open5GS("172.17.0.2", "27017")
    o5gs.removeAllSubscribers()
    with open(prj_folder + "/python_modules/subscriber_profile3.json", 'r') as f:
        profile = json.load(f)
    o5gs.addSubscriber(profile)

    info("\n*** Starting network\n")
    net.start()

    if not AUTOTEST_MODE:
        # spawnXtermDocker("open5gs")
        # spawnXtermDocker("gnb")
        # CLI(net)
        info("\n*** Waiting for the network to be ready... it can take some seconds\n")
        time.sleep(20)
        output = ue.cmd('ifconfig')

        while f"uesimtun{int(n_slices) - 1}" not in output:
            info("\n*** Still waiting...\n")
            time.sleep(5)
            output = ue.cmd('ifconfig')

        info("\n*** Testing connections\n")
        output = ue.cmd('ifconfig')
        info("\n*** Available interfaces:\n")
        print(output)

        info("\n*** Checking connectivity:\n")
        for i in range(int(n_slices)):
            output = ue.cmd(f'ping -c 3 -n -I uesimtun{i} www.google.com')
            print(output)

        info("\n*** Checking bandwidths:\n")
        for i in range(int(n_slices)):
            subnet = slices[i]['subnet']
            octets = subnet.split(".")
            octets[3] = str(int(octets[3]) + 1)
            new_address = ".".join(octets)
            output = ue.cmd(f'iperf3 -c {subnet} -B {new_address} -t 5')
            print(output)

        CLI(net)

    net.stop()
