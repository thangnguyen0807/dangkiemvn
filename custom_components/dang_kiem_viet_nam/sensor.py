"""Sensors for vehicle inspection information."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_BIENDANGKY, DOMAIN
from .coordinator import DangKiemCoordinator


@dataclass(frozen=True, kw_only=True)
class DangKiemSensorDescription(SensorEntityDescription):
    """Describe a vehicle inspection sensor."""

    field: str
    value_kind: str = "text"


SENSORS: tuple[DangKiemSensorDescription, ...] = (
    DangKiemSensorDescription(
        key="inspection_expiry",
        name="Ngày hết hạn kiểm định",
        field="HanKDtoi",
        value_kind="date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-alert",
    ),
    DangKiemSensorDescription(
        key="inspection_date",
        name="Ngày kiểm định",
        field="NgayKD",
        value_kind="date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-check",
    ),
    DangKiemSensorDescription(
        key="registration_date",
        name="Ngày đăng ký phương tiện",
        field="NgayDK",
        value_kind="date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar",
    ),
    DangKiemSensorDescription(
        key="days_until_expiry",
        name="Số ngày còn lại đến hạn kiểm định",
        field="HanKDtoi",
        value_kind="days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-clock",
    ),
    DangKiemSensorDescription(
        key="chassis_number",
        name="Số khung",
        field="SoKhung",
        icon="mdi:identifier",
    ),
    DangKiemSensorDescription(
        key="engine_number",
        name="Số động cơ",
        field="SoMay",
        icon="mdi:engine",
    ),
    DangKiemSensorDescription(
        key="brand",
        name="Nhãn hiệu",
        field="NhanHieu",
        icon="mdi:car-info",
    ),
    DangKiemSensorDescription(
        key="production_year",
        name="Năm sản xuất",
        field="NamSX",
        value_kind="integer",
        icon="mdi:calendar-month",
    ),
    DangKiemSensorDescription(
        key="inspection_report_number",
        name="Số phiếu kiểm định",
        field="SoPhieuKD",
        icon="mdi:file-document-outline",
    ),
    DangKiemSensorDescription(
        key="inspection_sticker_serial",
        name="Số seri tem kiểm định",
        field="SoTemGCN",
        icon="mdi:ticket-confirmation-outline",
    ),
    DangKiemSensorDescription(
        key="odometer_km",
        name="Số công-tơ-mét khi kiểm định",
        field="Odometer",
        value_kind="integer",
        native_unit_of_measurement="km",
        icon="mdi:counter",
    ),
    DangKiemSensorDescription(
        key="engine_displacement",
        name="Dung tích động cơ",
        field="DungTich",
        value_kind="integer",
        native_unit_of_measurement="cm³",
        icon="mdi:engine-outline",
    ),
    DangKiemSensorDescription(
        key="maximum_power",
        name="Công suất cực đại",
        field="Nmax",
        value_kind="integer",
        native_unit_of_measurement="kW",
        icon="mdi:lightning-bolt",
    ),
    DangKiemSensorDescription(
        key="power_rpm",
        name="Vòng tua tại công suất cực đại",
        field="VongQuay",
        value_kind="integer",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
    ),
    DangKiemSensorDescription(
        key="last_update_time",
        name="Thời gian cập nhật gần nhất",
        field="",
        value_kind="update_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
    ),
    DangKiemSensorDescription(
        key="update_result",
        name="Kết quả cập nhật",
        field="",
        value_kind="update_result",
        icon="mdi:cloud-check-outline",
    ),
)


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date or datetime from the XML."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_integer(value: str | None) -> int | None:
    """Parse a plain integer, returning None for empty or invalid values."""
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up inspection sensors for a configured vehicle."""
    coordinator: DangKiemCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Remove the old combined registration-plate sensor. Its value and
    # technical attributes are redundant now that individual sensors exist.
    registry = er.async_get(hass)
    obsolete_unique_id = f"{entry.entry_id}_registration_plate"
    obsolete_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, obsolete_unique_id
    )
    if obsolete_entity_id:
        registry.async_remove(obsolete_entity_id)

    async_add_entities(
        DangKiemSensor(coordinator, entry, description) for description in SENSORS
    )


class DangKiemSensor(CoordinatorEntity[DangKiemCoordinator], SensorEntity):
    """Represent one field from the vehicle inspection XML."""

    entity_description: DangKiemSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DangKiemCoordinator,
        entry: ConfigEntry,
        description: DangKiemSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        plate = (entry.data.get(CONF_BIENDANGKY) or "vehicle").strip().upper()
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=f"Xe {coordinator.data.get('BienDK', plate)}",
            manufacturer=coordinator.data.get("NhanHieu") or None,
            model="Thông tin đăng kiểm",
        )

    async def async_added_to_hass(self) -> None:
        """Register listeners only after Home Assistant assigns this entity."""
        await super().async_added_to_hass()
        if self.entity_description.key == "days_until_expiry":
            self.async_on_remove(
                async_track_time_change(
                    self.hass,
                    self._handle_midnight,
                    hour=0,
                    minute=0,
                    second=5,
                )
            )

    @property
    def available(self) -> bool:
        """Keep diagnostic sensors available when a refresh fails."""
        if self.entity_description.value_kind in {
            "update_timestamp",
            "update_result",
        }:
            return True
        return super().available

    @property
    def icon(self) -> str | None:
        """Show a status-appropriate icon for the update result sensor."""
        if self.entity_description.key == "update_result":
            if self.coordinator.last_update_result is True:
                return "mdi:check-circle"
            if self.coordinator.last_update_result is False:
                return "mdi:alert-circle"
            return "mdi:help-circle-outline"
        return self.entity_description.icon

    @property
    def native_value(self) -> date | datetime | str | int | None:
        """Return either vehicle data or update diagnostics."""
        kind = self.entity_description.value_kind

        if kind == "update_timestamp":
            return self.coordinator.last_update_attempt
        if kind == "update_result":
            if self.coordinator.last_update_result is True:
                return "Thành công"
            if self.coordinator.last_update_result is False:
                return "Thất bại"
            return None

        value = self.coordinator.data.get(self.entity_description.field)
        if kind == "date":
            return _parse_date(value)
        if kind == "integer":
            return _parse_integer(value)
        if kind == "days":
            expiry = _parse_date(value)
            if expiry is None:
                return None
            return (expiry - dt_util.now().date()).days
        return value or None

    @callback
    def _handle_midnight(self, now: datetime) -> None:
        """Refresh the remaining-days state after the local date changes."""
        self.async_write_ha_state()
