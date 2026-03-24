# core/url_context_helpers.py
#
# Shared URL-context helpers used by both framework_manager and Prebid tests
# (bidder presence, etc.) to derive publisher, environment, and page type
# from URLs and runner config.

from typing import Any
from urllib.parse import urlparse


def norm(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


def map_pagetype_to_db(page_type: str, liveblog: str) -> str:
    pt = (page_type or "").strip().lower()
    lb = (liveblog or "").strip().lower()

    if pt == "index":
        return "index"

    if pt == "video":
        if lb in ("y", "yes", "true", "1"):
            return "blog_article"
        return "video_article"

    if pt == "image":
        return "image_article"

    if pt == "gallery":
        return "gallery_article"

    return pt or "unknown"


def publisher_from_url(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    if host.endswith("independent.co.uk"):
        return "independent"
    if host.endswith("standard.co.uk"):
        return "standard"
    return "unknown"


def env_from_url(url: str) -> str:
    """staging is treated as uat (same bidders/cookies/auth per requirements)"""
    u = (url or "").lower()
    if "staging" in u:
        return "uat"
    if any(token in u for token in ("uat", "feat", "dev")):
        return "uat"
    return "prod"


def get_context_publisher(config: dict, url: str) -> str:
    """Prefer explicit runner context; fallback to URL heuristic."""
    pub = norm(config.get("publisher") or config.get("publication"))
    return pub if pub else publisher_from_url(url)


def get_context_environment(config: dict, url: str) -> str:
    """Prefer explicit runner context; fallback to URL heuristic."""
    env = norm(config.get("environment") or config.get("env"))
    return env.lower() if env else env_from_url(url)


def has_explicit_ctx(config: dict) -> bool:
    return bool(norm(config.get("publisher") or config.get("publication"))) or bool(
        norm(config.get("environment") or config.get("env"))
    )
