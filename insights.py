"""Print the account's reel stats by posting hour (no token is printed). Run by .github/workflows/insights.yml."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
API = "https://graph.facebook.com/v24.0"
TOKEN = os.environ["IG_TOKEN"].strip()
IG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "queue.json"), encoding="utf-8"))["ig_user_id"]


def get(path, **params):
    url = API + path + "?" + urllib.parse.urlencode(dict(params, access_token=TOKEN))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode("utf-8", "replace")[:300].replace(TOKEN, "<token>")}


print("account:", json.dumps(get("/" + IG, fields="followers_count,media_count")))
media = get("/%s/media" % IG, fields="id,timestamp,media_product_type,permalink,like_count,comments_count", limit=50).get("data", [])
for m in media:
    print(m["timestamp"], m.get("like_count"), m.get("comments_count"), m.get("permalink")); continue
    ins = get("/%s/insights" % m["id"], metric="views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time")
    vals = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])} or ins
    print(m["timestamp"], m.get("media_product_type"), m.get("permalink"), json.dumps(vals))
for metric, extra in (("online_followers", {"period": "lifetime"}),
                      ("follower_demographics", {"period": "lifetime", "metric_type": "total_value", "breakdown": "country"}),
                      ("follower_demographics", {"period": "lifetime", "metric_type": "total_value", "breakdown": "age"}),
                      ("engaged_audience_demographics", {"period": "lifetime", "metric_type": "total_value", "breakdown": "country", "timeframe": "this_month"})):
    print(metric, extra.get("breakdown", ""), json.dumps(get("/%s/insights" % IG, metric=metric, **extra))[:1500])
