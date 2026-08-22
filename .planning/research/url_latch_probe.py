#!/usr/bin/env python3
"""Does a seek in Kodi go back through a redirector, or straight to the redirect target?

This decides PLAY-06 and PLAY-07's priority, and it needs no OneDrive account, no
token, no network, and no Android device.

Background
----------
`CCurlFile::Open` ends with `m_url = efurl` — after following a redirect, Kodi keeps
the *effective* URL, not the one it was given. `CCurlFile::Seek` then re-sets
`CURLOPT_URL` from `m_url`. If that is what happens in practice, every seek goes
straight to the storage host and the loopback redirector never sees it, which means
a 302 redirector does not protect playback from an expiring URL — it only covers
the initial open and a reconnect that has not seeked yet.

That is a claim about Kodi's C++ core, so it is platform-independent and reproducible
on any desktop Kodi. This script reproduces it with two local servers and a generated
video file, so the answer costs five minutes instead of a phase.

How it works
------------
Two servers, deliberately on two different ports so the redirect crosses an origin
the way it does in production:

    redirector  127.0.0.1:8621/stream.mp4   ->  302  ->  media 127.0.0.1:8622/media/<file>
    media       127.0.0.1:8622/media/<file> ->  the bytes, with real Range support

Every request to either server is logged with a sequence number, method, path and
Range header. You play the redirector URL in Kodi, mark the point where playback is
running, seek a long way forward, and the script reports whether the redirector was
touched again.

Range support matters: without it Kodi cannot seek at all, and the test would measure
nothing. This serves 206 responses with a correct Content-Range.

This answers ONE of the two questions behind PLAY-06. It does not answer PLAY-06.

    Q1  Does a seek bypass the redirector?        <- this script
    Q2  How long does a real downloadUrl live?    <- url_lifetime_probe.py

Q1 only matters because of Q2. If Microsoft's URLs live for hours the latch is
harmless; if they live for minutes the latch is the whole problem. Run both.

Two configurations
------------------
`--target-url <a live @microsoft.graph.downloadUrl>` is the **production shape**: a
local 302 into a real remote host over https, with whatever further redirects that
host issues on its own. Prefer it. `url_lifetime_probe.py --print-url` hands you one.

Without it the script serves a generated file from a second local port. That still
tests the latch — the latch is `m_url = efurl` in Kodi's C++ and does not inspect the
URL — but it does not exercise the http->https scheme change or a redirect chain,
and over loopback the file arrives so fast that Kodi may buffer past any seek you
make, returning INCONCLUSIVE. Treat the local mode as a harness check, not as the
answer.

Usage
-----
    # 0. check the harness itself works, no Kodi involved
    python url_latch_probe.py --selftest

    # 1. generate a test video (needs ffmpeg; ~10 min, low bitrate, seekable)
    python url_latch_probe.py --make-media

    # 2a. production shape — what to actually trust
    python url_latch_probe.py --target-url "https://...files.1drv.com/..."

    # 2b. local shape — mechanism only
    python url_latch_probe.py

Then in Kodi: open the .strm the script writes, or paste the redirector URL into
Videos -> Files -> Add videos. Let it play, press Enter here, seek several minutes
forward, press Enter again.

Seek FAR. Kodi caches ahead, and a seek inside the cache issues no HTTP request at
all — that would look like "the redirector was not touched" for the wrong reason.
The script warns you if the media server saw no new request either, which is what a
too-short seek looks like.
"""

import argparse
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request

REDIRECT_PORT = 8621
MEDIA_PORT = 8622
STREAM_PATH = "/stream.mp4"
MEDIA_PREFIX = "/media/"

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MEDIA = os.path.join(HERE, "latch-probe-media.mp4")
DEFAULT_STRM = os.path.join(HERE, "latch-probe.strm")

_log_lock = threading.Lock()
_log = []


def record(server, method, path, range_header):
    with _log_lock:
        seq = len(_log) + 1
        entry = {
            "seq": seq,
            "t": time.time(),
            "server": server,
            "method": method,
            "path": path,
            "range": range_header,
        }
        _log.append(entry)
    rng = range_header or "-"
    print(f"  [{seq:>3}] {server:<10} {method:<5} {path:<28} Range: {rng}", flush=True)
    return entry


def snapshot():
    with _log_lock:
        return list(_log)


class Quiet(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass


class RedirectHandler(Quiet):
    media_url = ""

    def do_GET(self):
        record("redirector", "GET", self.path, self.headers.get("Range"))
        if self.path != STREAM_PATH:
            self.send_error(404)
            return
        self.send_response(302)
        self.send_header("Location", self.media_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        record("redirector", "HEAD", self.path, self.headers.get("Range"))
        self.send_response(302)
        self.send_header("Location", self.media_url)
        self.send_header("Content-Length", "0")
        self.end_headers()


class MediaHandler(Quiet):
    media_path = ""

    def _resolve(self):
        if not self.path.startswith(MEDIA_PREFIX):
            return None
        return self.media_path

    def do_HEAD(self):
        record("media", "HEAD", self.path, self.headers.get("Range"))
        path = self._resolve()
        if not path:
            self.send_error(404)
            return
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        record("media", "GET", self.path, range_header)
        path = self._resolve()
        if not path:
            self.send_error(404)
            return
        size = os.path.getsize(path)

        start, end = 0, size - 1
        partial = False
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
            if m:
                s, e = m.group(1), m.group(2)
                if s:
                    start = int(s)
                    end = int(e) if e else size - 1
                elif e:
                    start = max(0, size - int(e))
                    end = size - 1
                if start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                end = min(end, size - 1)
                partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        remaining = length
        with open(path, "rb") as fh:
            fh.seek(start)
            while remaining > 0:
                chunk = fh.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    # Kodi closes the connection on seek. That is the event we are
                    # here to observe, not an error.
                    return
                remaining -= len(chunk)


class Threaded(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_servers(media_path, target_url=None):
    """Start the redirector, and the local media server unless redirecting elsewhere.

    With `target_url` set the redirector points at a real remote URL — a live
    OneDrive `@microsoft.graph.downloadUrl` — which is the production shape and the
    only configuration that also exercises the http->https scheme change and any
    further redirect the storage host issues on its own.
    """
    RedirectHandler.media_url = target_url or (
        f"http://127.0.0.1:{MEDIA_PORT}{MEDIA_PREFIX}{os.path.basename(media_path)}"
    )

    red = Threaded(("127.0.0.1", REDIRECT_PORT), RedirectHandler)
    threading.Thread(target=red.serve_forever, daemon=True).start()
    if target_url:
        return red, None

    MediaHandler.media_path = media_path
    med = Threaded(("127.0.0.1", MEDIA_PORT), MediaHandler)
    threading.Thread(target=med.serve_forever, daemon=True).start()
    return red, med


def make_media(path, minutes):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it, or pass --media <your own video file>.")
    seconds = int(minutes * 60)
    print(f"Generating a {minutes:g}-minute test video at {path} ...")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-b:v", "400k", "-c:a", "aac", "-b:a", "64k",
        "-movflags", "+faststart",
        "-shortest", path,
    ]
    subprocess.run(cmd, check=True)
    size = os.path.getsize(path)
    print(f"Done: {size / 1024 / 1024:.1f} MB\n")


def selftest(media_path):
    print("Self-test: exercising the harness without Kodi.\n")
    start_servers(media_path)
    time.sleep(0.3)
    url = f"http://127.0.0.1:{REDIRECT_PORT}{STREAM_PATH}"

    print("1. GET the redirector, following the redirect:")
    with urllib.request.urlopen(url) as r:
        body = r.read(2048)
        effective = r.geturl()
    print(f"   -> followed to {effective}")
    print(f"   -> read {len(body)} bytes\n")

    print("2. Range request straight to the effective URL (what a latched seek does):")
    req = urllib.request.Request(effective, headers={"Range": "bytes=1000000-1000999"})
    with urllib.request.urlopen(req) as r:
        code, cr, n = r.status, r.headers.get("Content-Range"), len(r.read())
    print(f"   -> HTTP {code}, Content-Range: {cr}, {n} bytes\n")

    entries = snapshot()
    red = [e for e in entries if e["server"] == "redirector"]
    ranged = [e for e in entries if e["server"] == "media" and e["range"]]

    ok = code == 206 and cr is not None and n == 1000 and len(red) == 1 and len(ranged) == 1
    print("-" * 68)
    if ok:
        print("Self-test PASSED. Redirect works, Range works, and a request that goes")
        print("straight to the effective URL does not touch the redirector — which is")
        print("exactly the discrimination the real probe depends on.")
    else:
        print("Self-test FAILED. Fix the harness before trusting a Kodi result.")
        print(f"  206 expected, got {code}; Content-Range {cr}; {n} bytes (1000 expected)")
        print(f"  redirector hits {len(red)} (1 expected); ranged media hits {len(ranged)} (1 expected)")
    return 0 if ok else 1


def verdict(before, after, remote):
    new = after[len(before):]
    red_new = [e for e in new if e["server"] == "redirector"]
    med_new = [e for e in new if e["server"] == "media"]

    print()
    print("=" * 68)
    print("RESULT")
    print("=" * 68)
    print(f"Requests during the seek window: {len(new)}")
    print(f"  redirector : {len(red_new)}")
    if not remote:
        print(f"  media      : {len(med_new)}")
    print()

    if remote and not red_new:
        print("Note: the byte requests went straight to the remote host, so this script")
        print("cannot see them and cannot prove on its own that the seek caused any")
        print("network activity at all. Before trusting the verdict below, confirm the")
        print("seek was real: in kodi.log look for a fresh 'CCurlFile::Open' or")
        print("'FillBuffer - Reconnect' line at the moment you seeked. If there is none,")
        print("the seek landed in cache and this run measured nothing — seek further.")
        print()

    if not remote and not med_new:
        print("INCONCLUSIVE — the media server saw no request either.")
        print()
        print("The seek was served from Kodi's cache, so no HTTP happened at all and")
        print("nothing was measured. Re-run and seek much further forward, past what")
        print("Kodi has already buffered. Over loopback the whole file arrives almost")
        print("instantly, so this is the common outcome with a local target — running")
        print("with --target-url against a real remote URL avoids it.")
        return 2

    if red_new:
        print("SECOND REQUEST TO THE REDIRECTOR — Kodi re-resolved through loopback.")
        print()
        print("The latch does not hold end to end. SUMMARY.md Reconciled Conflicts #4")
        print("stands as originally written, and ANDROID-PLAYBACK-STORAGE.md section 1.5")
        print("is wrong and must be corrected. A redirector does cover seeks, so PLAY-06")
        print("does not hinge on the raw URL lifetime and PLAY-07 stays a confirmation")
        print("test rather than a decision gate.")
        return 1

    print("NO SECOND REQUEST — the latch is real end to end.")
    print()
    print("Kodi kept the effective URL after the redirect and seeked straight to the")
    print("media server, bypassing the redirector entirely. ANDROID-PLAYBACK-STORAGE.md")
    print("section 1.5 is confirmed: a 302 redirector does NOT protect a seek from an")
    print("expiring URL. PLAY-06 therefore depends on how long Microsoft's downloadUrl")
    print("actually lives, so PLAY-07 must run FIRST in Phase 6 — it decides whether")
    print("PLAY-06 is achievable with a redirector alone.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--media", default=DEFAULT_MEDIA, help="video file to serve")
    ap.add_argument("--make-media", action="store_true", help="generate the test video with ffmpeg and exit")
    ap.add_argument("--minutes", type=float, default=10.0, help="length of the generated video (default 10)")
    ap.add_argument("--selftest", action="store_true", help="verify the harness without Kodi")
    ap.add_argument(
        "--target-url",
        help="redirect to this URL instead of the local media server. Pass a live "
             "OneDrive @microsoft.graph.downloadUrl to run the probe in its production "
             "shape: a local 302 into a real remote host over https. Get one with "
             "url_lifetime_probe.py --print-url",
    )
    args = ap.parse_args()

    if args.make_media:
        make_media(args.media, args.minutes)
        return 0

    remote = bool(args.target_url)

    if not remote and not os.path.exists(args.media):
        print(f"No media file at {args.media}")
        print("Run:  python url_latch_probe.py --make-media")
        print("or:   python url_latch_probe.py --media <path to any video>")
        print("or:   python url_latch_probe.py --target-url <a real downloadUrl>")
        return 1

    if args.selftest:
        if remote:
            print("--selftest exercises the local media server; drop --target-url.")
            return 1
        return selftest(args.media)

    start_servers(args.media, args.target_url)
    time.sleep(0.3)
    url = f"http://127.0.0.1:{REDIRECT_PORT}{STREAM_PATH}"
    with open(DEFAULT_STRM, "w", encoding="utf-8") as fh:
        fh.write(url + "\n")

    print("=" * 68)
    print("URL LATCH PROBE" + ("  (production shape: real remote target)" if remote else "  (local target)"))
    print("=" * 68)
    print(f"Redirector : {url}")
    if remote:
        shown = args.target_url if len(args.target_url) <= 96 else args.target_url[:93] + "..."
        print(f"Redirects to: {shown}")
        print("Byte requests go straight to that host, so they do not appear below.")
        print("Only redirector hits are visible — which is exactly the signal wanted.")
    else:
        print(f"Redirects to: http://127.0.0.1:{MEDIA_PORT}{MEDIA_PREFIX}{os.path.basename(args.media)}")
        print(f"Media file : {args.media} ({os.path.getsize(args.media) / 1024 / 1024:.1f} MB)")
        print()
        print("Local target: the file arrives over loopback almost instantly, so Kodi may")
        print("buffer past any seek and the run returns INCONCLUSIVE. This configuration")
        print("tests the latch mechanism; --target-url tests it in production shape.")
    print(f"Playlist   : {DEFAULT_STRM}")
    print()
    print("In Kodi: play that .strm, or Videos -> Files -> Add videos -> paste the")
    print("redirector URL. Requests appear below as they arrive.")
    print("-" * 68)

    input("\n>> Start playback, let it run ~15 seconds, then press Enter here. ")
    before = snapshot()
    if not before:
        print("\nNothing has reached either server. Kodi is not playing the redirector URL.")
        return 1
    print(f"\nMarked. {len(before)} request(s) so far — that is the open, not the seek.")
    print("-" * 68)
    print("\nNow SEEK FORWARD several minutes in Kodi. Seek far — a short seek lands")
    print("inside Kodi's cache and issues no request, which measures nothing.")
    input("\n>> Press Enter once the seek has completed and playback resumed. ")

    time.sleep(1.0)
    return verdict(before, snapshot(), remote)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
