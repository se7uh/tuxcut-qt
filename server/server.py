from bottle import Bottle, response, request, run
import json
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from utils import *
import os

# Setup logging untuk terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log ke terminal
    ]
)

app = Bottle()
victims = list()
scheduler = BackgroundScheduler()

@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

@app.get('/status')
def status():
    return {'status': 'success'}

@app.get('/gw')
def get_gateway():
    gw = get_default_gw()
    if gw:
        return {'status': 'success', 'gw': gw}
    return {'status': 'error', 'msg': 'Computer is not connected'}

@app.get('/my/<iface>')
def get_my_info(iface):
    my = get_my(iface)
    if my:
        return {'status': 'success', 'my': my}
    return {'status': 'error', 'msg': 'Could not get interface information'}

@app.get('/scan/<ip>')
def scan_network(ip):
    ans, unans = arping(ip + '/24', verbose=0)
    hosts = list()
    for s, r in ans:
        host = dict()
        host['ip'] = r.psrc
        host['mac'] = r.hwsrc
        host['hostname'] = get_hostname(r.psrc)
        hosts.append(host)
    return {'status': 'success', 'result': {'hosts': hosts}}

@app.post('/cut')
def cut_victim():
    victim = request.json
    if victim not in victims:
        victims.append(victim)
        enable_ip_forward()
        arp_spoof(victim)
        return {'status': 'success'}
    return {'status': 'error', 'msg': 'Host already cut'}

@app.post('/resume')
def resume_victim():
    victim = request.json
    if victim in victims:
        victims.remove(victim)
        arp_unspoof(victim)
        if not victims:
            disable_ip_forward()
        return {'status': 'success'}
    return {'status': 'error', 'msg': 'Host is not cut'}

@app.get('/change-mac/<iface>')
def change_mac(iface):
    try:
        new_mac = generate_mac()
        sp.Popen(['ip', 'link', 'set', 'dev', iface, 'down'])
        sp.Popen(['ip', 'link', 'set', 'dev', iface, 'address', new_mac])
        sp.Popen(['ip', 'link', 'set', 'dev', iface, 'up'])
        return {'status': 'success', 'result': {'status': 'success', 'mac': new_mac}}
    except Exception as e:
        logger.error(sys.exc_info()[1], exc_info=True)
        return {'status': 'error', 'result': {'status': 'failed'}}

def spoof_victims():
    for victim in victims:
        arp_spoof(victim)

def start_server():
    try:
        scheduler.add_job(spoof_victims, 'interval', seconds=1, id='arp_spoof')
        scheduler.start()
        print("\n" + "="*50)
        print("TuxCut Qt Server v7.0")
        print("="*50)
        print("\nServer starting...")
        print("Listening on http://127.0.0.1:8013")
        print("\nLog output:")
        print("-"*50)
        run(app, host='127.0.0.1', port=8013, quiet=False)
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        scheduler.shutdown()
    except Exception as e:
        print(f"\nError: {str(e)}")
        scheduler.shutdown()

@app.post('/protect')
def protect_computer():
    try:
        gw = request.json
        enable_ip_forward()
        
        # Create fake ARP responses
        to_gw = ARP()
        to_gw.op = 2  # is-at
        to_gw.psrc = gw['ip']
        to_gw.hwsrc = gw['mac']
        to_gw.pdst = gw['ip']
        to_gw.hwdst = gw['mac']
        
        send(to_gw, count=5, verbose=0)
        logger.info('Protection enabled')
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Protection error: {str(e)}")
        return {'status': 'error', 'msg': str(e)}

@app.post('/unprotect')
def unprotect_computer():
    try:
        disable_ip_forward()
        logger.info('Protection disabled')
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Unprotection error: {str(e)}")
        return {'status': 'error', 'msg': str(e)}

@app.get('/log')
def get_log():
    try:
        log_file = '/var/log/tuxcut/tuxcut.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Get last 50 lines
                lines = f.readlines()[-50:]
                return {'status': 'success', 'log': ''.join(lines)}
        return {'status': 'error', 'log': 'Log file not found'}
    except Exception as e:
        logger.error(f"Error reading log: {str(e)}")
        return {'status': 'error', 'log': str(e)}

if __name__ == '__main__':
    start_server() 