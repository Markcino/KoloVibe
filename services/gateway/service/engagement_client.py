"""BE-EN integration seam. None means engagement data is unavailable.

The real client returns {video_id: nonnegative count}, a nonnegative follower
count, or an ordered list of video-id strings, respectively.
"""


def like_counts(video_ids):
    return None


def follower_count(creator_id):
    return None


def trending_video_ids(limit=20):
    return None
