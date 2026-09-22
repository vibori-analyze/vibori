"""Client for the public izbirkom.ru SPA API."""

import json
import re
import threading
import time
from typing import Any, TypeAlias
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request

JsonObject: TypeAlias = dict[str, Any]


class ApiError(RuntimeError):
    def __init__(self, status: int, path: str, body: str) -> None:
        super().__init__(f"API {status} for {path}: {body[:500]}")
        self.status = status
        self.path = path


class IzbirkomApi:
    def __init__(
        self,
        opener: Any,
        base_url: str,
        user_agent: str,
        timeout: int = 45,
        retries: int = 3,
    ) -> None:
        self.opener = opener
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.api_key: str | None = None
        self._auth_lock = threading.Lock()

    def _json(
        self,
        path: str,
        *,
        data: JsonObject | None = None,
        authenticated: bool = False,
    ) -> JsonObject:
        headers = {
            "Accept": "application/json",
            "Connection": "close",
            "User-Agent": self.user_agent,
        }
        payload = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(data).encode()
        if authenticated:
            headers["X-Api-Key"] = self.api_key or ""
            headers["X-Client-Fingerprint"] = self.user_agent
        for attempt in range(self.retries):
            request = Request(self.base_url + path, data=payload, headers=headers)
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    return json.load(response)
            except HTTPError as error:
                body = error.read().decode(errors="replace")
                retry_server_error = error.code == 500 and path.startswith(
                    ("/challenge/", "/elections?")
                )
                if (
                    error.code in (429, 502, 503, 504) or retry_server_error
                ) and attempt + 1 < self.retries:
                    time.sleep(min(2**attempt, 15))
                    continue
                raise ApiError(error.code, path, body) from error
            except OSError:
                if attempt + 1 == self.retries:
                    raise
                time.sleep(min(2**attempt, 15))
        raise RuntimeError(f"API request exhausted retries for {path}")

    @staticmethod
    def _solve_task(task: str) -> int:
        match = re.fullmatch(r"return\s+(\d+)\s*([+*-])\s*(\d+)\s*;", task)
        if not match:
            raise RuntimeError("Unsupported API challenge")
        left, right = int(match[1]), int(match[3])
        return {"+": left + right, "-": left - right, "*": left * right}[match[2]]

    def authenticate(self) -> None:
        with self._auth_lock:
            challenge = self._json("/challenge/get")
            solved = self._json(
                "/challenge/solve",
                data={
                    "pubToken": challenge["pubToken"],
                    "answer": str(self._solve_task(challenge["jsTask"])),
                    "fingerprint": self.user_agent,
                },
            )
            self.api_key = solved["apiKey"]

    def get(self, path: str, params: JsonObject | None = None) -> JsonObject:
        if not self.api_key:
            self.authenticate()
        query = "?" + urlencode(params, doseq=True) if params else ""
        try:
            return self._json(path + query, authenticated=True)
        except ApiError as error:
            if error.status not in (401, 403):
                raise
            self.authenticate()
            return self._json(path + query, authenticated=True)

    def elections(
        self,
        date_from: str,
        date_to: str,
        page: int = 1,
        per_page: int = 100,
    ) -> JsonObject:
        return self.get(
            "/elections",
            {
                "votingDateFrom": date_from,
                "votingDateTo": date_to,
                "page": page,
                "perPage": per_page,
            },
        )
