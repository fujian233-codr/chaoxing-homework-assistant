from __future__ import annotations

from typing import Protocol

import keyring


SERVICE_NAME = "chaoxing-homework-checker"


class SecretStore(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...


class KeyringStore:
    def get_password(self, service: str, username: str) -> str | None:
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        keyring.set_password(service, username, password)


def account_password_key(account_id: str) -> str:
    return f"account:{account_id}:password"


def get_account_password(account_id: str, store: SecretStore | None = None) -> str | None:
    store = store or KeyringStore()
    return store.get_password(SERVICE_NAME, account_password_key(account_id))


def set_account_password(account_id: str, password: str, store: SecretStore | None = None) -> None:
    store = store or KeyringStore()
    store.set_password(SERVICE_NAME, account_password_key(account_id), password)


def get_webhook(webhook_ref: str, store: SecretStore | None = None) -> str | None:
    store = store or KeyringStore()
    return store.get_password(SERVICE_NAME, f"webhook:{webhook_ref}")


def set_webhook(webhook_ref: str, webhook: str, store: SecretStore | None = None) -> None:
    store = store or KeyringStore()
    store.set_password(SERVICE_NAME, f"webhook:{webhook_ref}", webhook)
