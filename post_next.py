"""Post the next queued BLOODPACT reel to Instagram (Graph API, Instagram content publishing).

    python post_next.py            # post the first queue item that has no "posted_at"
    python post_next.py --dry-run  # show what would be posted
    python post_next.py --force    # post even if the last post was under 115 minutes ago
    python post_next.py --wait     # sleep until the next item's post_at (at most WAIT_MAX), post nothing
    python post_next.py --pending  # exit 0 if a timed item (post_at) is still unposted, else 1

An item may carry "post_at" (UTC, "YYYY-MM-DDTHH:MM:SSZ"): it is not posted before that time. Items without it
keep the old rule (the next run at least 115 minutes after the last post). An item may carry its own "url"
instead of base_url + file.

Env: IG_TOKEN (a user token with instagram_content_publish), IG_USER_ID (the Instagram account id).
Locally the token can come from IG_TOKEN_FILE (a KEY=value file with IG_ACCESS_TOKEN=...).
The token is never printed: every line this script prints goes through scrub().
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue.json")
API = "https://graph.facebook.com/v24.0"
# a GitHub job may run 6 hours; the workflow starts the next run when this one ends
WAIT_MAX = int(os.environ.get("WAIT_MAX_MIN") or 300) * 60
UTC = datetime.timezone.utc


def parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def load_token():
    tok = os.environ.get("IG_TOKEN", "").strip()
    path = os.environ.get("IG_TOKEN_FILE")
    if not tok and path and os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            if line.strip().startswith("IG_ACCESS_TOKEN="):
                tok = line.split("=", 1)[1].strip().strip("\"'")
    if not tok:
        raise SystemExit("no IG_TOKEN")
    return tok


TOKEN = None


def scrub(text):
    text = str(text)
    return text.replace(TOKEN, "<token>") if TOKEN else text


def call(method, path, params):
    data = dict(params, access_token=TOKEN)
    url = API + path
    body = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(data)
    else:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit("API %s %s failed (%d): %s" % (method, path, e.code, scrub(e.read().decode("utf-8", "replace")[:600])))


def main():
    global TOKEN
    dry = "--dry-run" in sys.argv
    q = json.load(open(QUEUE, encoding="utf-8"))
    if "--pending" in sys.argv:
        sys.exit(0 if any(p.get("post_at") and not p.get("posted_at") for p in q["posts"]) else 1)
    item = next((p for p in q["posts"] if not p.get("posted_at")), None)
    if not item:
        print("queue empty: nothing to post")
        return
    video_url = item.get("url") or q["base_url"] + item["file"]
    print("next:", item["file"], "at", item.get("post_at", "the next run"))
    now = datetime.datetime.now(UTC)
    if item.get("post_at"):
        wait = (parse(item["post_at"]) - now).total_seconds()
        if "--wait" in sys.argv:
            if wait > 0:
                print("sleeping %d min" % (min(wait, WAIT_MAX) // 60), flush=True)
                time.sleep(min(wait, WAIT_MAX))
            return
        if wait > 60 and "--force" not in sys.argv:
            print("not due for %d min" % (wait // 60))
            return
        if wait < -3600:
            print("late by %d min (a run was missed)" % (-wait // 60))
    elif "--wait" in sys.argv:
        return
    last = max((p["posted_at"] for p in q["posts"] if p.get("posted_at")), default=None)
    if last and "--force" not in sys.argv:
        ago = now - parse(last)
        if ago < datetime.timedelta(minutes=100 if item.get("post_at") else 115):
            print("last post was %d min ago: waiting for the next run" % (ago.total_seconds() // 60))
            return
    if dry:
        print(item["caption"])
        return
    TOKEN = load_token()
    ig = os.environ.get("IG_USER_ID") or q["ig_user_id"]
    c = call("POST", "/%s/media" % ig, {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": item["caption"],
        "share_to_feed": "true",
        "thumb_offset": str(item.get("cover_ms", 0)),
    })
    cid = c["id"]
    print("container", cid)
    status = None
    for _ in range(60):  # up to 10 minutes for Instagram to fetch and process the video
        time.sleep(10)
        s = call("GET", "/%s" % cid, {"fields": "status_code,status"})
        status = s.get("status_code")
        if status in ("FINISHED", "ERROR", "EXPIRED"):
            break
    if status != "FINISHED":
        raise SystemExit("container not ready: %s %s" % (status, scrub(s.get("status"))))
    m = call("POST", "/%s/media_publish" % ig, {"creation_id": cid})
    mid = m["id"]
    info = call("GET", "/%s" % mid, {"fields": "permalink,timestamp"})
    item["posted_at"] = datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    item["media_id"] = mid
    item["permalink"] = info.get("permalink")
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("posted:", item["permalink"])


if __name__ == "__main__":
    main()
