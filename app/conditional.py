"""HTTP conditional request support (ETags, If-None-Match, If-Match).

Validators are derived from the optimistic-locking ``version`` counters, so
cache revalidation and lost-update protection share a single source of truth.
"""

import hashlib
from collections.abc import Callable, Coroutine, Iterable
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute

RESPONSE_HEADERS_ETAG: dict[str, object] = {
    "ETag": {
        "description": (
            "Version-based validator; send it back via If-None-Match for "
            "conditional GET or If-Match for updates and deletes."
        ),
        "schema": {"type": "string"},
    }
}


def _quoted(value: str) -> str:
    return f'"{value}"'


def _short_hash(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


def _split_etags(header: str) -> list[str]:
    return [candidate.strip() for candidate in header.split(",") if candidate.strip()]


def _strip_weak_prefix(etag: str) -> str:
    return etag.removeprefix("W/")


def etag_for(kind: str, resource_id: int, version: int) -> str:
    """ETag for a versioned single resource."""
    return _quoted(f"{kind}-{resource_id}-v{version}")


def etag_for_children(
    kind: str,
    resource_id: int,
    version: int,
    children: Iterable[tuple[int, int]],
) -> str:
    """ETag for a resource whose representation embeds versioned children.

    Used for binder detail (nested cards), so any card change invalidates it.
    """
    fingerprint = ",".join(
        f"{child_id}:{child_version}" for child_id, child_version in children
    )
    return _quoted(f"{kind}-{resource_id}-v{version}-{_short_hash(fingerprint)}")


def etag_for_collection(kind: str, items: Iterable[tuple[int, int]]) -> str:
    """ETag of an ordered collection fingerprint of ``(id, version)`` pairs."""
    fingerprint = ",".join(f"{item_id}:{version}" for item_id, version in items)
    return _quoted(f"{kind}-{_short_hash(fingerprint)}")


def etag_for_search(hits: Iterable[tuple[int, int, str]]) -> str:
    """ETag of ranked search hits including their binder names."""
    fingerprint = "\x1f".join(
        f"{card_id}:{version}:{binder_name}" for card_id, version, binder_name in hits
    )
    return _quoted(f"search-{_short_hash(fingerprint)}")


def etag_for_immutable(kind: str, resource_id: int) -> str:
    """ETag for an immutable single resource."""
    return _quoted(f"{kind}-{resource_id}")


def etag_for_immutable_collection(kind: str, ids: Iterable[int]) -> str:
    """ETag of an ordered id fingerprint for immutable rows."""
    fingerprint = ",".join(str(resource_id) for resource_id in ids)
    return _quoted(f"{kind}-{_short_hash(fingerprint)}")


def if_none_match_matches(header: str | None, etag: str) -> bool:
    """Weak comparison per RFC 9110, used for If-None-Match."""
    if not header:
        return False
    candidates = _split_etags(header)
    if "*" in candidates:
        return True
    target = _strip_weak_prefix(etag)
    return any(_strip_weak_prefix(candidate) == target for candidate in candidates)


def if_match_matches(header: str | None, etag: str) -> bool:
    """Strong comparison per RFC 9110, used for If-Match.

    Weak validators (``W/"..."``) never match because the request must be
    conditional on the exact representation state.
    """
    if not header:
        return False
    candidates = _split_etags(header)
    if "*" in candidates:
        return True
    return any(candidate == etag for candidate in candidates)


def enforce_if_match(if_match: str | None, current_etag: str) -> None:
    """Enforce a matching If-Match header, raising 428/412 otherwise.

    Must only be called after the target resource was successfully loaded, so
    a missing resource still yields a 404.
    """
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required: send the ETag from the last GET",
        )
    if not if_match_matches(if_match, current_etag):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Precondition failed: current ETag is {current_etag}",
        )


class ConditionalGetRoute(APIRoute):
    """Route class adding ETag revalidation and caching headers to GET responses."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def conditional_handler(request: Request) -> Response:
            response = await original_handler(request)
            if request.method != "GET" or response.status_code != status.HTTP_200_OK:
                return response
            response.headers["Cache-Control"] = "no-cache"
            etag = response.headers.get("etag")
            if etag is not None and if_none_match_matches(
                request.headers.get("if-none-match"), etag
            ):
                return Response(
                    status_code=status.HTTP_304_NOT_MODIFIED,
                    headers={"ETag": etag, "Cache-Control": "no-cache"},
                )
            return response

        return conditional_handler
