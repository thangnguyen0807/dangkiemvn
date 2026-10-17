"""Data coordinator for the Đăng kiểm Việt Nam integration."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DangKiemApiError, async_fetch_vehicle
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DangKiemCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Fetch inspection data and track the latest update attempt/result."""

    def __init__(self, hass: HomeAssistant, query: dict[str, str]) -> None:
        self.query = query
        self.session = async_get_clientsession(hass)
        self.last_update_attempt = None
        self.last_update_result: bool | None = None
        self._was_already_failed_before_attempt = False
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            # Notify timestamp diagnostics even if the XML data has not changed.
            always_update=True,
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the latest XML and record the attempt time and result."""
        self._was_already_failed_before_attempt = not self.last_update_success
        self.last_update_attempt = dt_util.utcnow()
        try:
            result = await async_fetch_vehicle(self.session, self.query)
        except DangKiemApiError as err:
            self.last_update_result = False
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_update_result = False
            raise UpdateFailed(
                "Unable to connect to the vehicle inspection website"
            ) from err
        except Exception:
            # Keep diagnostic status accurate even for an unexpected parser or runtime error.
            self.last_update_result = False
            raise

        self.last_update_result = True
        return result

    @callback
    def _async_refresh_finished(self) -> None:
        """Notify diagnostic entities when consecutive refreshes all fail.

        The coordinator normally avoids notifying listeners on repeated failures.
        We still notify because the attempt timestamp and diagnostic status changed.
        """
        if (
            not self.last_update_success
            and self._was_already_failed_before_attempt
        ):
            self.async_update_listeners()
