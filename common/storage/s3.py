"""
Stockage objet compatible S3 pour les médias EVENTFLOW.

Fonctionne avec :
    - Cloudflare R2
    - Supabase Storage (API S3)
    - Backblaze B2
    - Amazon S3
    - MinIO / tout service compatible S3

Pourquoi ce backend maison plutôt que django-storages ?
    - Aucune dépendance supplémentaire (donc aucun risque d'incompatibilité
      avec Django 6.1) : la signature AWS Signature Version 4 est implémentée
      avec la bibliothèque standard (hashlib, hmac, urllib).
    - Le projet n'a besoin que de PUT / GET / HEAD / DELETE, ce qui reste
      simple et suffisant.

⚠️ Le stockage n'est activé que si `AWS_STORAGE_BUCKET_NAME` est défini
(voir settings.py). Sinon Django continue d'utiliser le disque local.

Variables attendues (voir .env.example) :
    AWS_STORAGE_BUCKET_NAME   nom du bucket
    AWS_S3_ENDPOINT_URL       endpoint S3 du fournisseur
    AWS_ACCESS_KEY_ID         clé d'accès
    AWS_SECRET_ACCESS_KEY     secret
    AWS_S3_REGION_NAME        région ("auto" pour R2)
    AWS_S3_PUBLIC_URL         URL publique de base (si bucket public)
    AWS_S3_QUERYSTRING_EXPIRE durée de validité des URL signées (secondes)
"""

from __future__ import annotations

import hashlib
import hmac
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from io import BytesIO

from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

_UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
_ALGORITHM = "AWS4-HMAC-SHA256"


def _quote(value: str, safe: str = "~") -> str:
    """Encodage RFC 3986 exigé par AWS (espace => %20, pas +)."""
    return urllib.parse.quote(str(value), safe=safe)


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


@deconstructible
class S3Storage(Storage):
    """Backend Django Storage minimal pour un service compatible S3."""

    def __init__(self, **kwargs):
        self.bucket_name = kwargs.get("bucket_name") or getattr(
            settings, "AWS_STORAGE_BUCKET_NAME", ""
        )
        self.endpoint_url = (
            kwargs.get("endpoint_url") or getattr(settings, "AWS_S3_ENDPOINT_URL", "")
        ).rstrip("/")
        self.access_key = kwargs.get("access_key") or getattr(
            settings, "AWS_ACCESS_KEY_ID", ""
        )
        self.secret_key = kwargs.get("secret_key") or getattr(
            settings, "AWS_SECRET_ACCESS_KEY", ""
        )
        self.region_name = (
            kwargs.get("region_name")
            or getattr(settings, "AWS_S3_REGION_NAME", "")
            or "auto"
        )
        self.public_url = (
            kwargs.get("public_url") or getattr(settings, "AWS_S3_PUBLIC_URL", "")
        ).rstrip("/")
        self.querystring_expire = int(
            kwargs.get("querystring_expire")
            or getattr(settings, "AWS_S3_QUERYSTRING_EXPIRE", 3600)
        )

        if not (self.bucket_name and self.endpoint_url and self.access_key and self.secret_key):
            raise ValueError(
                "Stockage S3 incomplet : AWS_STORAGE_BUCKET_NAME, "
                "AWS_S3_ENDPOINT_URL, AWS_ACCESS_KEY_ID et "
                "AWS_SECRET_ACCESS_KEY sont obligatoires."
            )

        parsed = urllib.parse.urlsplit(self.endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"AWS_S3_ENDPOINT_URL invalide : {self.endpoint_url!r}. "
                "Attendu : https://hote[/chemin]."
            )

        self._scheme = parsed.scheme
        self._host = parsed.netloc
        self._base_path = parsed.path.rstrip("/")

    # ------------------------------------------------------------------
    # CHEMINS / URL
    # ------------------------------------------------------------------
    def _object_path(self, name: str) -> str:
        key = str(name).lstrip("/")
        return f"{self._base_path}/{_quote(self.bucket_name, safe='~')}/{_quote(key, safe='/~')}"

    def _object_url(self, name: str) -> str:
        return f"{self._scheme}://{self._host}{self._object_path(name)}"

    def url(self, name: str) -> str:
        """
        URL publique si `AWS_S3_PUBLIC_URL` est configurée, sinon URL signée.

        Les URL signées fonctionnent aussi pour un bucket privé (utile pour
        les images de couverture sans rendre tout le bucket public).
        """
        if self.public_url:
            return f"{self.public_url}/{_quote(str(name).lstrip('/'), safe='/~')}"
        return self._presigned_url(name)

    # ------------------------------------------------------------------
    # SIGNATURE AWS V4
    # ------------------------------------------------------------------
    def _signing_key(self, date_stamp: str) -> bytes:
        key = _hmac(("AWS4" + self.secret_key).encode("utf-8"), date_stamp)
        key = _hmac(key, self.region_name)
        key = _hmac(key, "s3")
        return _hmac(key, "aws4_request")

    def _canonical_query(self, query: dict) -> str:
        return "&".join(
            f"{_quote(key)}={_quote(value)}"
            for key, value in sorted(query.items())
        )

    def _sign_request(
        self,
        method: str,
        canonical_uri: str,
        query: dict,
        headers: dict,
        payload_hash: str,
    ) -> tuple[str, str]:
        """
        Calcule la signature de la requête.

        Returns:
            (valeur du header Authorization, valeur de x-amz-date)
        """
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.region_name}/s3/aws4_request"

        headers = {key.lower(): str(value).strip() for key, value in headers.items()}
        headers["host"] = self._host
        headers["x-amz-content-sha256"] = payload_hash
        headers["x-amz-date"] = amz_date

        canonical_headers = "".join(
            f"{key}:{headers[key]}\n" for key in sorted(headers)
        )
        signed_headers = ";".join(sorted(headers))

        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                self._canonical_query(query),
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        string_to_sign = "\n".join(
            [
                _ALGORITHM,
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return (
            (
                f"{_ALGORITHM} Credential={self.access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
            amz_date,
        )

    def _presigned_url(self, name: str) -> str:
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.region_name}/s3/aws4_request"
        canonical_uri = self._object_path(name)

        query = {
            "X-Amz-Algorithm": _ALGORITHM,
            "X-Amz-Credential": f"{self.access_key}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(self.querystring_expire),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = self._canonical_query(query)
        canonical_headers = f"host:{self._host}\n"

        canonical_request = "\n".join(
            [
                "GET",
                canonical_uri,
                canonical_query,
                canonical_headers,
                "host",
                _UNSIGNED_PAYLOAD,
            ]
        )
        string_to_sign = "\n".join(
            [
                _ALGORITHM,
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        query["X-Amz-Signature"] = signature
        return (
            f"{self._scheme}://{self._host}{canonical_uri}"
            f"?{self._canonical_query(query)}"
        )

    # ------------------------------------------------------------------
    # REQUÊTES HTTP
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        name: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
    ):
        canonical_uri = self._object_path(name)
        payload = body or b""
        payload_hash = hashlib.sha256(payload).hexdigest()

        headers: dict[str, str] = {}
        if content_type:
            headers["content-type"] = content_type

        authorization, amz_date = self._sign_request(
            method, canonical_uri, {}, headers, payload_hash
        )

        request = urllib.request.Request(
            self._object_url(name),
            data=body,
            method=method,
        )
        for key, value in headers.items():
            request.add_header(key, value)
        request.add_header("Authorization", authorization)
        request.add_header("x-amz-content-sha256", payload_hash)
        request.add_header("x-amz-date", amz_date)

        try:
            return urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # pragma: no cover - lecture best-effort
                pass
            raise OSError(
                f"Erreur stockage S3 ({method} {name}) : HTTP {exc.code} {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OSError(
                f"Stockage S3 injoignable ({method} {name}) : {exc.reason}"
            ) from exc

    # ------------------------------------------------------------------
    # API Django Storage
    # ------------------------------------------------------------------
    def _save(self, name: str, content) -> str:
        if hasattr(content, "seek"):
            content.seek(0)
        if hasattr(content, "chunks"):
            body = b"".join(content.chunks())
        else:
            body = content.read()

        content_type = (
            mimetypes.guess_type(str(name))[0] or "application/octet-stream"
        )
        response = self._request(
            "PUT", name, body=body, content_type=content_type
        )
        response.close()
        return name

    def _open(self, name: str, mode: str = "rb"):
        if mode not in {"rb", "r"}:
            raise ValueError("Le stockage S3 ne supporte que la lecture binaire.")
        response = self._request("GET", name)
        try:
            return BytesIO(response.read())
        finally:
            response.close()

    def delete(self, name: str) -> None:
        try:
            response = self._request("DELETE", name)
        except OSError as exc:
            # Supprimer un fichier déjà absent n'est pas une erreur.
            if "HTTP 404" in str(exc):
                return
            raise
        response.close()

    def exists(self, name: str) -> bool:
        try:
            response = self._request("HEAD", name)
        except OSError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise
        response.close()
        return True

    def size(self, name: str) -> int:
        response = self._request("HEAD", name)
        try:
            return int(response.headers.get("Content-Length", 0))
        finally:
            response.close()

    def listdir(self, path: str):
        raise NotImplementedError(
            "listdir() n'est pas implémenté pour le stockage S3 EVENTFLOW."
        )

    def get_modified_time(self, name: str):
        response = self._request("HEAD", name)
        try:
            last_modified = response.headers.get("Last-Modified")
        finally:
            response.close()
        if not last_modified:
            return None
        return datetime.strptime(
            last_modified, "%a, %d %b %Y %H:%M:%S %Z"
        ).replace(tzinfo=timezone.utc)
