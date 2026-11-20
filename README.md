# bloodpact-social

Posts BLOODPACT (Roblox) reels to Instagram @bloodpactroblox, one every 2 hours.

- `queue.json`: the posts in order. The first item without `posted_at` is next.
- `post_next.py`: posts it via the Instagram Graph API and marks it posted.
- `.github/workflows/post.yml`: runs `post_next.py` every 2 hours (and on demand from the Actions tab).
- Videos are attached to this repo's releases; `base_url` in the queue points at them.
- The token is the repo secret `IG_TOKEN`. It expires after about 60 days; generate a new one in the Meta app
  (Instagram API, Unified login) and set the secret again.

To pause posting: Actions tab → "Post next reel" → ⋯ → Disable workflow.
