"""Config flow for Đăng kiểm Việt Nam."""

from __future__ import annotations

import asyncio
import logging
import re

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DangKiemApiError, async_fetch_vehicle
from .const import (
    CONF_BIENDANGKY,
    CONF_LOAIPT,
    CONF_SOKHUNG,
    DEFAULT_LOAIPT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DangKiemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a user-provided vehicle lookup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Collect vehicle lookup data and test the remote endpoint."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = {key: str(value).strip() for key, value in user_input.items()}
            if not cleaned.get(CONF_BIENDANGKY) or not cleaned.get(CONF_SOKHUNG):
                errors["base"] = "invalid_input"
            else:
                try:
                    data = await async_fetch_vehicle(
                        async_get_clientsession(self.hass), cleaned
                    )
                except DangKiemApiError as err:
                    # Log the safe, sanitized reason. Never log query data or XML.
                    _LOGGER.warning("Vehicle inspection lookup failed: %s", err)
                    errors["base"] = "cannot_connect"
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    _LOGGER.warning(
                        "Vehicle inspection lookup failed with %s",
                        type(err).__name__,
                    )
                    errors["base"] = "cannot_connect"
                else:
                    normalized_plate = re.sub(
                        r"[^A-Z0-9]", "", cleaned[CONF_BIENDANGKY].upper()
                    )
                    await self.async_set_unique_id(normalized_plate)
                    self._abort_if_unique_id_configured()
                    plate = data.get("BienDK") or cleaned[CONF_BIENDANGKY]
                    brand = data.get("NhanHieu", "").strip()
                    title = f"Đăng kiểm {plate}"
                    if brand:
                        title = f"{title} ({brand})"
                    return self.async_create_entry(title=title, data=cleaned)

        schema = vol.Schema(
            {
                vol.Required(CONF_BIENDANGKY): str,
                vol.Required(CONF_SOKHUNG): str,
                vol.Required(CONF_LOAIPT, default=DEFAULT_LOAIPT): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
