#!/usr/bin/env python3
"""
Verify an Azure app registration works for the OneDrive Kodi add-on's sign-in.

Runs the exact protocol the add-on will use: OAuth 2.0 device authorization
grant (RFC 8628) against the Microsoft identity platform, then proves the
resulting token can actually list OneDrive drives.

Standard library only, on purpose -- this is the same constraint the add-on
runs under inside Kodi.

Usage:
    python verify_device_code.py --client-id <GUID>
    python verify_device_code.py --client-id <GUID> --authority consumers
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCOPES = "https://graph.microsoft.com/Files.Read offline_access openid profile"
GRAPH = "https://graph.microsoft.com/v1.0"
TIMEOUT = 30

# RFC 8628 says keep polling ONLY on these. Anything else is terminal.
# This is an allow-list on purpose: Microsoft returns undocumented error
# codes, so a deny-list would loop forever on a real failure.
CONTINUE_ON = {"authorization_pending", "slow_down"}


def post_form(url, fields):
    """POST a form. Returns (status, parsed_json).

    Microsoft returns HTTP 400 with a JSON body for ordinary protocol states
    like authorization_pending, so a 4xx is NOT necessarily a failure here.
    """
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": "non_json_response", "raw": raw[:400].decode(errors="replace")}


def get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:400].decode(errors="replace")}


def decode_id_token(id_token):
    """Read the id_token payload for display only. No signature check --
    this is a diagnostic, not an authorization decision."""
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def banner(text):
    print("\n" + "=" * 68)
    print(text)
    print("=" * 68)


# The two failure branches below used to print the failing response and drop it.
# That discard is how an earlier observed failure was lost, and the response
# class it discards -- a tenant that refuses the grant outright -- is precisely
# the one this project cannot produce on demand, because the tenant hosting this
# registration permits the grant. So the response gets kept instead.
CAPTURE_PREFIX = "device-code-failure-"
CAPTURE_SUFFIX = ".json"
CAPTURE_COLLISION_LIMIT = 100


def capture_failure(stage, status, body, authority):
    """Write a failing response to a file beside this script. Returns its path.

    Nothing is redacted, on purpose. This file is written by a maintainer on
    their own machine into a path git is told to ignore, and the fields a
    redactor would strip are the ones a diagnosis needs. The ignore rule for
    this filename pattern is what keeps it local, and it landed in the same
    commit as this function -- so a capture cannot be committed by accident.

    The name carries a timestamp, and a collision inside the same second takes
    a counter, so a second run can never overwrite the first run's evidence.
    """
    record = {
        "stage": stage,
        "moment": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authority": authority,
        "status": status,
        "response": body,
    }
    directory = os.path.dirname(os.path.abspath(__file__))
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())

    for attempt in range(CAPTURE_COLLISION_LIMIT):
        tail = "" if attempt == 0 else "-%d" % attempt
        path = os.path.join(
            directory, CAPTURE_PREFIX + stamp + tail + CAPTURE_SUFFIX)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        except OSError as e:
            print(f"\n  (the failing response could not be saved: {e})")
            return None
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
        return path

    print("\n  (the failing response could not be saved: too many captures in "
          "the same second)")
    return None


def report_capture(path):
    """Say where the response went, or say nothing if it went nowhere."""
    if path:
        print(f"\n  Failing response saved, unredacted, to:\n    {path}")
        print("  git is told to ignore that name. Read it where it is; do not")
        print("  paste its contents into anything tracked.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True, help="Application (client) ID from the portal")
    ap.add_argument(
        "--authority",
        default="common",
        choices=["common", "consumers", "organizations"],
        help="common = both account types (what the add-on should use)",
    )
    args = ap.parse_args()

    base = f"https://login.microsoftonline.com/{args.authority}/oauth2/v2.0"

    banner(f"STEP 1  Request a device code   (authority: /{args.authority})")

    status, dc = post_form(
        base + "/devicecode", {"client_id": args.client_id, "scope": SCOPES}
    )

    if "device_code" not in dc:
        print(f"FAILED  HTTP {status}")
        print(json.dumps(dc, indent=2))
        report_capture(capture_failure("devicecode", status, dc, args.authority))
        print("\nCommon causes:")
        print("  AADSTS700016  client_id not found in this authority -- check the GUID,")
        print("                and check signInAudience really is")
        print("                AzureADandPersonalMicrosoftAccount")
        print("  AADSTS500011  the scope's resource is not in this tenant")
        return 1

    # verification_uri differs per authority. Never hardcode it.
    print(f"  expires_in : {dc.get('expires_in')} seconds")
    print(f"  interval   : {dc.get('interval')} seconds")
    print(f"  complete?  : {'verification_uri_complete' in dc}   (Microsoft does not support this)")

    banner("STEP 2  Authorize")
    print(f"\n  Open:  {dc['verification_uri']}")
    print(f"\n  Code:  {dc['user_code']}\n")
    print("  Sign in with the account you want to test.")
    print("  Watch the consent screen -- note the app name and the exact")
    print("  permissions listed. That is what your users will see.\n")

    interval = int(dc.get("interval", 5))
    deadline = time.time() + int(dc.get("expires_in", 900))
    started = time.time()

    while True:
        if time.time() > deadline:
            print("\nFAILED  the code expired before it was entered")
            return 1

        time.sleep(interval)
        status, tok = post_form(
            base + "/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": args.client_id,
                "device_code": dc["device_code"],
            },
        )

        if "access_token" in tok:
            break

        err = tok.get("error", "")
        if err == "slow_down":
            interval += 5  # RFC 8628: the increase is permanent
            print(f"  slow_down -> interval now {interval}s")
            continue
        if err in CONTINUE_ON:
            print(f"  waiting... ({int(time.time() - started)}s)")
            continue

        # Terminal. This is the branch that matters most for the add-on:
        # whatever appears here is what a blocked tenant looks like, and the
        # add-on has to turn it into one clear sentence on a TV.
        print(f"\nFAILED  HTTP {status}  error={err}")
        print(json.dumps(tok, indent=2))
        report_capture(capture_failure("token-poll", status, tok, args.authority))
        print("\nWrite this error code down -- the add-on needs to map it to")
        print("a specific message pointing at the custom client_id setting.")
        print("  AADSTS7000218  'Allow public client flows' is still No")
        print("  AADSTS65001    user or admin has not consented")
        print("  AADSTS50105/53003  Conditional Access is blocking device code flow")
        print("  AADSTS7000014  the device_code was rejected")
        return 1

    elapsed = int(time.time() - started)
    banner(f"STEP 3  Token acquired in {elapsed}s")

    print(f"  token_type    : {tok.get('token_type')}")
    print(f"  expires_in    : {tok.get('expires_in')} seconds")
    print(f"  refresh_token : {'YES' if tok.get('refresh_token') else 'NO -- offline_access missing!'}")
    print(f"  id_token      : {'YES' if tok.get('id_token') else 'no'}")
    print(f"  scopes granted: {tok.get('scope')}")

    if not tok.get("refresh_token"):
        print("\n  WARNING: no refresh_token. Without it the add-on re-prompts")
        print("  every hour, which on a TV reads as total failure.")

    claims = decode_id_token(tok.get("id_token", ""))
    if claims:
        print("\n  Account identity (from id_token, for labelling accounts):")
        print(f"    name : {claims.get('name')}")
        print(f"    upn  : {claims.get('preferred_username')}")
        print(f"    sub  : {claims.get('sub')}   <- stable per-account key")
        print(f"    tid  : {claims.get('tid')}")

    banner("STEP 4  Which drive-enumeration endpoints actually work?")

    # Graph's reference implies /me/drives serves both account classes.
    # It does not: a personal Microsoft account gets 403 accessDenied.
    # Probe every candidate so the add-on can branch on evidence rather
    # than on documentation.
    token = tok["access_token"]
    results = {}
    drive = None

    for path in ("/me/drives", "/me/drive", "/drives"):
        status, body = get_json(GRAPH + path, token)
        results[path] = status
        mark = "OK  " if status == 200 else "FAIL"
        detail = ""
        if status != 200:
            detail = "  " + str((body.get("error") or {}).get("code", body))[:60]
        print(f"  {mark} {status}  GET {path}{detail}")

        if status == 200 and drive is None:
            # /me/drives returns a collection; /me/drive returns one object.
            drive = (body.get("value") or [None])[0] if "value" in body else body

    if drive is None:
        print("\nFAILED  no drive-enumeration endpoint worked for this account")
        return 1

    print(f"\n  Usable drive:")
    print(f"    driveType : {drive.get('driveType')}")
    print(f"    id        : {drive.get('id')}")
    print(f"    owner     : {(drive.get('owner') or {}).get('user', {}).get('displayName')}")

    banner("STEP 5  Prove a folder actually lists")

    did = drive["id"]
    status, kids = get_json(f"{GRAPH}/drives/{did}/root/children?$top=8", token)
    if status != 200:
        print(f"  FAIL {status}  GET /drives/{{id}}/root/children")
        print(json.dumps(kids, indent=2))
        print("\n  Retrying via /me/drive/root/children ...")
        status, kids = get_json(f"{GRAPH}/me/drive/root/children?$top=8", token)
        if status != 200:
            print(f"  FAIL {status}  that path too")
            print(json.dumps(kids, indent=2))
            return 1
        print("  OK   /me/drive/root/children works where /drives/{id}/ did not")

    for c in kids.get("value", []):
        kind = "DIR " if "folder" in c else "FILE"
        print(f"    {kind} {c.get('name')}")

    print(f"\n  Endpoint support for this account type: {json.dumps(results)}")

    banner("PASS")
    print(f"""
  authority /{args.authority} works with this client_id, for this account type.

  Run this a second time with the OTHER account type before treating the
  authority choice as settled -- a personal account passing says nothing
  about a work account, and vice versa.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
