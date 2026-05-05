from fastapi import FastAPI
from pydantic import BaseModel
import requests
import time

app = FastAPI()

ZAP_HOST = "http://zap:8080"
SPIDER_MAX_WAIT_SECONDS = 300
ACTIVE_SCAN_MAX_WAIT_SECONDS = 900  


class ScanRequest(BaseModel):
    target: str


def wait_for_zap(max_wait=120):
    print("Waiting for ZAP to be ready...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            r = requests.get(f"{ZAP_HOST}/JSON/core/view/version/")
            if r.status_code == 200:
                print("ZAP is ready.")
                return
        except Exception as e:
            pass

        time.sleep(3)

    raise RuntimeError("ZAP not ready after waiting 120 seconds")

def wait_for_spider(scan_id, timeout=SPIDER_MAX_WAIT_SECONDS):
    start_time = time.time()
    while time.time() - start_time < timeout:
        r = requests.get(
            f"{ZAP_HOST}/JSON/spider/view/status/",
            params={"scanId": scan_id},
            timeout=10,
        )
        status = int(r.json().get("status", 0))
        print(f"[SPIDER] scan_id={scan_id} progress={status}%")
        if status >= 100:
            return True
        time.sleep(2)
    return False


def wait_for_active_scan(scan_id, timeout=ACTIVE_SCAN_MAX_WAIT_SECONDS):
    start_time = time.time()
    while time.time() - start_time < timeout:
        r = requests.get(
            f"{ZAP_HOST}/JSON/ascan/view/status/",
            params={"scanId": scan_id},
            timeout=30,
        )
        status = int(r.json().get("status", 0))
        print(f"[ACTIVE_SCAN] scan_id={scan_id} progress={status}%")
        if status >= 100:
            return True
        time.sleep(3)
    return False

def wait_for_alerts(target, timeout=60):
    print("[ZAP] Waiting for alerts to stabilize...")
    start_time = time.time()
    last_count = -1

    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{ZAP_HOST}/JSON/core/view/alerts/",
                params={"baseurl": target},
                timeout=30,
            )
            alerts = response.json().get("alerts", [])
            current_count = len(alerts)

            print(f"[ZAP] Alerts count: {current_count}")

            # If count stops increasing → done
            if current_count == last_count:
                print("[ZAP] Alerts stabilized.")
                return alerts

            last_count = current_count

        except Exception as e:
            print("[ZAP] Error fetching alerts:", e)

        time.sleep(3)

    print("[ZAP] Alert wait timeout reached.")
    return alerts


@app.post("/execute")
def execute_scan(request: ScanRequest):

    wait_for_zap()

    target = request.target
    print(f"[ZAP] Starting scan for target={target}")

    #  Start spider
    spider_response = requests.get(
        f"{ZAP_HOST}/JSON/spider/action/scan/",
        params={
            "url": target,
            "maxChildren": 50,
        },
        timeout=30,
    )
    scan_id = spider_response.json().get("scan")
    print(f"[ZAP] Spider ID: {scan_id}")

    if not scan_id:
        return {"error": "Failed to start spider scan"}
    if not wait_for_spider(scan_id):
        return {"error": f"Spider timeout after {SPIDER_MAX_WAIT_SECONDS}s", "scan_id": scan_id}

    # Start active scan
    ascan_response = requests.get(
        f"{ZAP_HOST}/JSON/ascan/action/scan/",
        params={"url": target},
        timeout=30,
    )
    ascan_id = ascan_response.json().get("scan")
    print(f"[ZAP] Active Scan ID: {ascan_id}")

    if not ascan_id:
        return {"error": "Failed to start active scan"}
    if not wait_for_active_scan(ascan_id):
        return {"error": f"Active scan timeout after {ACTIVE_SCAN_MAX_WAIT_SECONDS}s", "scan_id": ascan_id}

    #  Fetch alerts
    alerts = wait_for_alerts(target)

    
    filtered_alerts = []

    for alert in alerts[:20]:
        filtered_alerts.append({
            "name": alert.get("name"),
            "risk": alert.get("risk"),
            "confidence": alert.get("confidence"),
            "url": alert.get("url"),
            "description": (alert.get("description") or "")[:500],
            "solution": (alert.get("solution") or "")[:300],
        })

    return {
        "total_alerts": len(alerts),
        "returned_alerts": len(filtered_alerts),
        "alerts": filtered_alerts,
    }