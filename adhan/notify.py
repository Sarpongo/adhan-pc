"""Notifications natives Windows (centre de notifications)."""

from __future__ import annotations

import base64
import logging
import subprocess
import threading
from xml.sax.saxutils import escape

from .paths import ICON_PNG

log = logging.getLogger(__name__)

APP_ID = "AdhanPC.Desktop"
APP_DISPLAY_NAME = "Adhan PC"

_CREATE_NO_WINDOW = 0x08000000
_registered = False

_PS_TEMPLATE = """
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
{payload}
'@)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""


def register_app_id() -> None:
    """Declare l'AUMID pour que la notification affiche le nom de l'application."""
    global _registered
    if _registered:
        return
    try:
        import winreg

        key_path = rf"Software\Classes\AppUserModelId\{APP_ID}"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
            if ICON_PNG.exists():
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(ICON_PNG))
            winreg.SetValueEx(key, "ShowInSettings", 0, winreg.REG_DWORD, 1)
        _registered = True
    except OSError as exc:
        log.warning("enregistrement AppUserModelID impossible : %s", exc)


def _build_xml(title: str, body: str, sub: str = "", silent: bool = True) -> str:
    logo = ""
    if ICON_PNG.exists():
        logo = (
            f'<image placement="appLogoOverride" hint-crop="circle" '
            f'src="{escape(str(ICON_PNG))}"/>'
        )
    lines = f"<text>{escape(title)}</text><text>{escape(body)}</text>"
    if sub:
        lines += f'<text placement="attribution">{escape(sub)}</text>'
    audio = '<audio silent="true"/>' if silent else '<audio src="ms-winsoundevent:Notification.Default"/>'
    return (
        '<toast activationType="protocol" launch="">'
        f'<visual><binding template="ToastGeneric">{lines}{logo}</binding></visual>'
        f"{audio}</toast>"
    )


def _run_powershell(script: str) -> None:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("notification native impossible : %s", exc)


def toast(title: str, body: str, sub: str = "", silent: bool = True) -> None:
    """Affiche une notification Windows (asynchrone, sans bloquer l'interface)."""
    register_app_id()
    script = _PS_TEMPLATE.format(payload=_build_xml(title, body, sub, silent), app_id=APP_ID)
    threading.Thread(target=_run_powershell, args=(script,), daemon=True).start()
