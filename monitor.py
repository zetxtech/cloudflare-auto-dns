import random
import re
import time
import telnetlib
from typing import Iterable, List

import yaml
import requests
from cloudflare import Cloudflare
from cloudflare.types.dns import Record
from loguru import logger

cache = {}
with open("config.yml") as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)
    
def task(init = False):
    global config
    cf = None
    for r in config['records']:
        domain: str = r['domain'].strip('.')
        subdomain: str = r['subdomain'].strip('.')
        if subdomain.endswith("." + domain):
            name = subdomain
        elif subdomain == "@":
            name = domain
        else:
            name = f'{subdomain}.{domain}'
        if init:
            if not cf:
                cf = Cloudflare(api_token=config['cloudflare']['token'])
            zone_id = get_zone_id(cf, domain)
            if not zone_id:
                continue
        else:
            zone_id = None
        if check(r['checks']):
            if name in cache:
                cache[name] = 0
        else:
            if name in cache:
                cache[name] += 1
            else:
                cache[name] = 1
        if cache.get(name, 0) < 3:
            continue
        
        if not cf:
            cf = Cloudflare(api_token=config['cloudflare']['token'])
        if not zone_id:
            zone_id = get_zone_id(cf, domain)
            if not zone_id:
                continue
        record_types = ["CNAME", "A", "AAAA"]
        dns_records: List[Record] = []
        for record_type in record_types:
            records = cf.dns.records.list(zone_id=zone_id, type=record_type, name=name)
            if records:
                dns_records.extend(records)
        if not dns_records:
            logger.warning(f"No DNS records found for '{name}'.")
            continue
        
        current_record = dns_records[0]
        current_type = current_record.type.upper()
        current_content = current_record.content
        
        pool = r['pool']
        other = []
        for p in pool:
            if p["type"].upper().strip() == current_type:
                if p["content"] == current_content:
                    continue
            other.append(p)
        if not other:
            logger.warning(f"No available source for '{name}'.")
            continue
        
        new_record = random.choice(other)
        record_id = current_record.id
        response = cf.dns.records.edit(
            zone_id=zone_id,
            dns_record_id=record_id,
            type=new_record["type"],
            name=name,
            content=new_record["content"],
            ttl=1,
        )
        if response:
            logger.success(f"Changed DNS for '{name}' from '{current_type} {current_content}' to '{new_record['type']} {new_record['content']}'.")
            cache[name] = 0
    
def get_zone_id(cf: Cloudflare, domain: str):
    zones = cf.zones.list(name=domain)
    if zones and len(zones) > 0:
        return zones[0]['id']
    else:
        logger.warning(f"Zone ID for {domain} not found.")
        return None

def to_iterable(var):
    if var is None:
        return ()
    if isinstance(var, str) or not isinstance(var, Iterable):
        return (var,)
    else:
        return var

def check(name: str, check_config: dict):
    for c in check_config:
        if c['type'] == 'web':
            if not check_web(
                target = c.get('target', f'http://{name}'),
                timeout = c.get('timeout', 10),
                status = c.get('status', '200-299'),
                regex = c.get('regex', None),
            ):
                return False
        elif c['type'] == 'ping':
            if not check_ping(
                host = c.get('target', name),
                max_latency = c.get('max_latency', 2000),
            ):
                return False
        elif c['type'] == 'tcping':
            if check_tcping(
                host = c.get('target', name),
                port = c.get('port', 80),
                timeout = c.get('timeout', 2000),
            ):
                return False
    return True
    
def check_web(target, timeout, status, regex):
    try:
        if regex:
            resp = requests.get(target, timeout=timeout)
        else:
            resp = requests.head(target, timeout=timeout)
    except:
        return False
    if status:
        for status_spec in str(status).split(','):
            status_spec = status_spec.strip()
            if '-' in status_spec:
                try:
                    status_from, status_to = status_spec.split('-')
                except ValueError:
                    logger.error(f"Wrong status config, invalid multiple '-' in record '{status_spec}'.")
                try:
                    if int(status_from) < resp.status_code < int(status_to):
                        break
                except ValueError:
                    logger.error(f"Wrong status config, invalid character in record '{status_spec}'.")
            else:
                try:
                    if int(status_from) == resp.status_code:
                        break
                except ValueError:
                    logger.error(f"Wrong status config, invalid character in record '{status_spec}'.")
        else:
            logger.info(f"Test '{target}' failed due to status {resp.status_code}.")
            return False
    if regex:
        for regex in to_iterable(regex):
            if re.search(regex, resp.content):
                break
        else:
            logger.info(f"Test '{target}' failed due to content regex not match.")
            return False

def check_ping(host, max_latency):
    from pythonping import ping
    
    ping_result = ping(target=host, count=4, timeout=int(max_latency+1))
    if ping_result.rtt_avg_ms > max_latency * 1000:
        return False
    else:
        return True

def check_tcping(host, port, max_latency):
    try:
        telnetlib.Telnet(host=host, port=port, timeout=max_latency)
        return True
    except:
        return False

def main():
    init = True
    while True:
        try:
            task(init)
            init = False
        except Exception as e:
            logger.opt(exception=e).error('Error occurs:')
        time.sleep(60)

if __name__ == "__main__":
    main()
