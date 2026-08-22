#!/usr/bin/env python3
"""How long does a OneDrive @microsoft.graph.downloadUrl stay usable? (PLAY-07)

This is the half of the playback question that needs a real account, and it is the
half that decides PLAY-06. `url_latch_probe.py` answers whether a Kodi seek bypasses
a 302 redirector; that only matters because of the answer here. If these URLs live
for hours, the latch is harmless. If they live for minutes, the latch is the whole
problem and a redirector alone cannot carry PLAY-06.

Microsoft documents the lifetime only as "short-lived", which is not a number you can
design against. So measure it.

Method
------
Sign in with device code (same flow, same scopes, same authority as the add-on),
pick a file, read its `@microsoft.graph.downloadUrl`, then poll that URL with a
one-byte Range request at a fixed interval until it stops returning 206. The last
success before the first failure bounds the lifetime.

A one-byte Range costs essentially nothing and does not download the file, so this
can run for hours against a large item without moving real traffic. It is also
exactly what Kodi does on a seek — a ranged GET to the latched URL — so a failure
here is the same failure a user would see mid-playback.

Note the URL is a pre-authenticated capability: it carries its own signature and is
fetched with **no** Authorization header. Sending the bearer token to it would
measure the wrong thing, so this script deliberately does not.

Usage
-----
    # measure it — the useful run
    python url_lifetime_probe.py --client-id <GUID>

    # just hand me a live URL to feed url_latch_probe.py --target-url
    python url_lifetime_probe.py --client-id <GUID> --print-url

    # personal account
    python url_lifetime_probe.py --client-id <GUID> --authority consumers

Leave it running. It prints a line per poll and a bounded answer at the end. Ctrl-C
reports what it has established so far rather than discarding it.
"""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = "https://graph.microsoft.com/Files.Read offline_access openid profile"
DOWNLOAD_URL_KEY = "@microsoft.graph.downloadUrl"


def post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"error": f"http_{e.code}"}


def get_json(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sign_in(client_id, authority):
    base = f"https://login.microsoftonline.com/{authority}/oauth2/v2.0"
    dc = post_form(base + "/devicecode", {"client_id": client_id, "scope": SCOPES})
    if "device_code" not in dc:
        print("Could not start device code flow:", dc.get("error_description", dc))
        sys.exit(1)

    print("=" * 68)
    print(f"  Go to : {dc['verification_uri']}")
    print(f"  Code  : {dc['user_code']}")
    print("=" * 68)

    interval = int(dc.get("interval", 5))
    deadline = time.time() + int(dc.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(interval)
        tok = post_form(base + "/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
            "device_code": dc["device_code"],
        })
        if "access_token" in tok:
            print("Signed in.\n")
            return tok["access_token"]
        err = tok.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        print("Sign-in failed:", tok.get("error_description", err))
        sys.exit(1)
    print("Device code expired.")
    sys.exit(1)


def pick_item(token, item_id=None):
    """Find something worth probing — the largest file we can see, or a named item."""
    if item_id:
        return get_json(f"{GRAPH}/me/drive/items/{item_id}?select=id,name,size,{DOWNLOAD_URL_KEY}", token)

    print("Looking for the largest file in the drive root ...")
    data = get_json(f"{GRAPH}/me/drive/root/children?select=id,name,size,file&$top=200", token)
    files = [c for c in data.get("value", []) if c.get("file")]
    if not files:
        print("No files in the drive root. Pass --item-id <id> for a file in a subfolder.")
        sys.exit(1)
    biggest = max(files, key=lambda c: c.get("size", 0))
    print(f"Using: {biggest['name']}  ({biggest.get('size', 0) / 1024 / 1024:.1f} MB)\n")
    return get_json(
        f"{GRAPH}/me/drive/items/{biggest['id']}?select=id,name,size,{DOWNLOAD_URL_KEY}", token
    )


def probe(url):
    """One-byte ranged GET, no Authorization header. Returns (ok, detail)."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 206, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__


def wait_visibly(seconds):
    """Sleep, but keep saying so.

    A silent five-minute gap between poll lines is indistinguishable from a hang,
    and the natural reaction is to kill the run — which discards the elapsed time
    that is the entire measurement. So count down in place.
    """
    end = time.time() + seconds
    while True:
        left = end - time.time()
        if left <= 0:
            break
        mins, secs = divmod(int(left), 60)
        print(f"\r    next poll in {mins:d}:{secs:02d} ...", end="", flush=True)
        time.sleep(min(1.0, left))
    print("\r" + " " * 40 + "\r", end="", flush=True)


def report(started, last_ok, first_fail, detail, interval):
    print()
    print("=" * 68)
    print("RESULT — PLAY-07")
    print("=" * 68)
    if last_ok is None:
        print("The URL never worked. Something is wrong with the fetch, not the lifetime.")
        return 1

    ok_min = (last_ok - started) / 60.0
    if first_fail is None:
        print(f"Still valid after {ok_min:.1f} minutes — no expiry observed ({detail}).")
        print()
        print("A lower bound, not the lifetime. Re-run for longer if you need the")
        print("actual number, but a bound is often enough to decide: if it already")
        print("exceeds a realistic pause-and-seek, PLAY-06 is safe with a redirector")
        print("alone and PLAY-07 goes back to being a confirmation test.")
        return 0

    fail_min = (first_fail - started) / 60.0
    print(f"Expired between {ok_min:.1f} and {fail_min:.1f} minutes ({detail}).")
    print(f"Poll interval was {interval / 60:.1f} min, so that is the resolution.")
    print()
    print("What this decides:")
    if fail_min < 40:
        print(f"  SHORT ({fail_min:.0f} min). ROADMAP Phase 6 asks for a pause of 20-30")
        print("  minutes followed by a seek. That lands at or past expiry, so if the")
        print("  latch probe also shows seeks bypassing the redirector, PLAY-06 CANNOT")
        print("  pass with a 302 redirector alone — the redirector must re-resolve, or")
        print("  something must re-issue the URL. Treat that as an architecture change")
        print("  and schedule it before PLAY-02/PLAY-03 are called done.")
    else:
        print(f"  COMFORTABLE ({fail_min:.0f} min). Longer than the pause PLAY-06 asks")
        print("  for, so the latch is survivable and the redirector design stands as")
        print("  written. Record the number; do not round it up.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--authority", default="common", choices=["common", "consumers", "organizations"])
    ap.add_argument("--item-id", help="probe this item instead of the largest root file")
    ap.add_argument("--interval", type=float, default=5.0, help="minutes between polls (default 5)")
    ap.add_argument("--max-hours", type=float, default=12.0, help="give up after this long (default 12)")
    ap.add_argument("--print-url", action="store_true", help="print a live downloadUrl and exit")
    args = ap.parse_args()

    token = sign_in(args.client_id, args.authority)
    item = pick_item(token, args.item_id)
    url = item.get(DOWNLOAD_URL_KEY)
    if not url:
        print("Graph returned no downloadUrl for that item.")
        return 1

    if args.print_url:
        print(url)
        return 0

    host = urllib.parse.urlparse(url).netloc
    print(f"Probing {item.get('name')} via {host}")
    print(f"Poll every {args.interval:g} min, give up after {args.max_hours:g} h.")
    print("A one-byte Range each time, no Authorization header — the URL carries its own.\n")

    started = time.time()
    deadline = started + args.max_hours * 3600
    interval = args.interval * 60
    last_ok = None
    detail = ""

    try:
        while time.time() < deadline:
            ok, detail = probe(url)
            mins = (time.time() - started) / 60.0
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"  [{stamp}] +{mins:6.1f} min  {'ok ' if ok else 'FAIL'}  {detail}", flush=True)
            if ok:
                last_ok = time.time()
            else:
                return report(started, last_ok, time.time(), detail, interval)
            wait_visibly(interval)
        return report(started, last_ok, None, detail, interval)
    except KeyboardInterrupt:
        print("\nStopped early.")
        return report(started, last_ok, None, detail, interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
