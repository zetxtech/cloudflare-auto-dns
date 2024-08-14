import os
import random
import re
import sys
import time
import telnetlib
from typing import Iterable, List

import yaml
import schema
import requests
from cloudflare import Cloudflare
from cloudflare.types.dns import Record
from loguru import logger

cache = {}
with open("config.yml") as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)

sch = schema.Schema(
    {
        "cloudflare": {"token": str},
        schema.Optional("debug"): bool,
        schema.Optional("interval"): schema.Or(float, int),
        schema.Optional("retries"): int,
        "records": [
            {
                "domain": str,
                "subdomain": str,
                "checks": [
                    schema.Or(
                        {
                            "type": "web",
                            schema.Optional("target"): str,
                            schema.Optional("timeout"): schema.Or(float, int),
                            schema.Optional("status"): schema.Or(str, int),
                            schema.Optional("regex"): str,
                        },
                        {
                            "type": "ping",
                            schema.Optional("target"): str,
                            schema.Optional("percentage"): schema.Or(float, int),
                        },
                        {
                            "type": "tcping",
                            schema.Optional("target"): str,
                            schema.Optional("port"): int,
                            schema.Optional("timeout"): schema.Or(float, int),
                        },
                    )
                ],
                "pool": [
                    {
                        "type": schema.And(
                            str,
                            schema.Use(str.upper),
                            lambda s: s in ("CNAME", "A", "AAAA"),
                        ),
                        "content": str,
                        schema.Optional("proxied"): bool,
                    }
                ],
            }
        ],
    }
)
sch.validate(config)


def task(init=False):
    global config
    cf = None
    for r in config["records"]:
        domain: str = r["domain"].strip(".")
        subdomain: str = r["subdomain"].strip(".")
        if subdomain.endswith("." + domain):
            name = subdomain
        elif subdomain == "@":
            name = domain
        else:
            name = f"{subdomain}.{domain}"
        if init:
            if not cf:
                cf = Cloudflare(api_token=config["cloudflare"]["token"])
            zone_id = get_zone_id(cf, domain)
            if not zone_id:
                continue
            dns_records = get_records(cf, zone_id, name)
            if not dns_records:
                logger.warning(f"No A/AAAA/CNAME DNS records found for '{name}'.")
                continue
            current_record = dns_records[0]
            current_type = current_record.type.upper()
            current_content = current_record.content
            logger.info(f"Current DNS record found for '{name}': '{current_type} {current_content}'.")
        else:
            zone_id = None
        if check(name, r["checks"]):
            if name in cache:
                cache[name] = 0
        else:
            if name in cache:
                cache[name] += 1
            else:
                cache[name] = 1
            logger.trace(f'Check failed, count {cache[name]}.')
        if cache.get(name, 0) < 3:
            continue

        if not cf:
            cf = Cloudflare(api_token=config["cloudflare"]["token"])
        if not zone_id:
            zone_id = get_zone_id(cf, domain)
            if not zone_id:
                continue
        
        dns_records = get_records(cf, zone_id, name)
        if not dns_records:
            logger.warning(f"No A/AAAA/CNAME DNS records found for '{name}'.")
            continue
        
        current_record = dns_records[0]
        current_type = current_record.type.upper()
        current_content = current_record.content

        pool = r["pool"]
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
            proxied=new_record.get("proxied", False),
            ttl=1,
        )
        if response:
            logger.success(
                f"Changed DNS for '{name}' from '{current_type} {current_content}' to '{new_record['type']} {new_record['content']}'."
            )
            cache[name] = 0


def get_zone_id(cf: Cloudflare, domain: str):
    zones = cf.zones.list(name=domain).result
    if len(zones) > 0:
        return zones[0].id
    else:
        logger.warning(f"Zone ID for '{domain}' not found.")
        return None

def get_records(cf: Cloudflare, zone_id, name):
    record_types = ["CNAME", "A", "AAAA"]
    dns_records: List[Record] = []
    for record_type in record_types:
        records = cf.dns.records.list(
            zone_id=zone_id, type=record_type, name=name
        ).result
        dns_records.extend(records)
    return dns_records

    current_record = dns_records[0]


def to_iterable(var):
    if var is None:
        return ()
    if isinstance(var, str) or not isinstance(var, Iterable):
        return (var,)
    else:
        return var


def check(name: str, check_config: dict):
    for c in check_config:
        if c["type"] == "web":
            if not check_web(
                target=c.get("target", f"http://{name}"),
                timeout=c.get("timeout", 10),
                status=c.get("status", "200-299"),
                regex=c.get("regex", None),
            ):
                return False
        elif c["type"] == "ping":
            if not check_ping(
                host=c.get("target", name),
                percentage=c.get("percentage", 0.8),
            ):
                return False
        elif c["type"] == "tcping":
            if not check_tcping(
                host=c.get("target", name),
                port=c.get("port", 80),
                timeout=c.get("timeout", 2000),
            ):
                return False
    return True


def check_web(target, timeout, status, regex):
    try:
        if regex:
            resp = requests.get(target, timeout=timeout, allow_redirects=True)
        else:
            resp = requests.head(target, timeout=timeout, allow_redirects=True)
    except Exception as e:
        logger.info(f"Test '{target}' failed due to: {e.__class__.__name__}: {e}.")
        return False
    if status:
        for status_spec in str(status).split(","):
            status_spec = status_spec.strip()
            if "-" in status_spec:
                try:
                    status_from, status_to = status_spec.split("-")
                except ValueError:
                    logger.error(
                        f"Wrong status config, invalid multiple '-' in record '{status_spec}'."
                    )
                try:
                    if int(status_from) <= resp.status_code <= int(status_to):
                        break
                except ValueError:
                    logger.error(
                        f"Wrong status config, invalid character in record '{status_spec}'."
                    )
            else:
                try:
                    if int(status_from) == resp.status_code:
                        break
                except ValueError:
                    logger.error(
                        f"Wrong status config, invalid character in record '{status_spec}'."
                    )
        else:
            logger.info(f"Test '{target}' failed due to status {resp.status_code}.")
            return False
    if regex:
        for regex in to_iterable(regex):
            if re.search(regex, resp.content.decode()):
                break
        else:
            logger.info(f"Test '{target}' failed due to content regex not match.")
            return False
    logger.trace(f"Check passed: web: '{target}'.")
    return True


def check_ping(host, percentage):
    if "linux" in sys.platform:
        x = os.popen("ping %s -c 5" % (host,))
        ping = x.read()
        x.close()
        r = int(ping.split("%")[0].split(",")[-1].strip())
        if r >= percentage:
            logger.info(f"Test '{host}' failed due to {r}% ping package lost.")
            return False
    elif "win" in sys.platform:
        x = os.popen("ping %s -n 5" % (host,))
        ping = x.read()
        x.close()
        r = int(ping.split("%")[0].split("(")[-1].strip())
        if r >= percentage:
            logger.info(f"Test '{host}' failed due to {r}% ping package lost.")
            return False
    logger.trace(f"Check passed: ping: '{host}'.")
    return True


def check_tcping(host, port, timeout):
    try:
        telnetlib.Telnet(host=host, port=port, timeout=timeout)
        logger.trace(f"Check passed: tcping: '{host}'.")
        return True
    except:
        logger.info(f"Test '{host}' failed due tcping timeout ({timeout} s).")
        return False

def main():
    global config
    if config.get('debug', False):
        logger.remove()
        logger.add(sys.stderr, level=0)
    logger.info("Cloudflare Auto DNS Started.")
    init = True
    while True:
        try:
            task(init)
            init = False
        except Exception as e:
            logger.opt(exception=e).error("Error occurs:")
        time.sleep(int(config.get("interval", 60)))


if __name__ == "__main__":
    main()
