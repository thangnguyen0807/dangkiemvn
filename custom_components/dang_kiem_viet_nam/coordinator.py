"""Data coordinator for the Đăng kiểm Việt Nam integration."""

from __future__ import annotations

import logging
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DangKiemApiError, async_fetch_vehicle
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DangKiemCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Fetch inspection data on a schedule and share it with entities."""

    def __init__(self, hass: HomeAssistant, query: dict[str, str]) -> None:
        self.query = query
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from the website."""
        try:
            return await async_fetch_vehicle(self.session, self.query)
        except DangKiemApiError as err:
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed("Unable to connect to the vehicle inspection website") from err
