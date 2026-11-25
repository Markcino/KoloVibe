def metadata(visibility="public", owned=False):
    """Content's item fields. The owner's own view also carries the edit review state (Decision A)."""
    return {"visibility": visibility, "published_at": None, "poster_url": None,
            "category": None, "tags": [], "cover_time_ms": None, **({"edit_review": None} if owned else {})}
