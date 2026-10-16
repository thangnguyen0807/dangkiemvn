"""Constants for the Đăng kiểm Việt Nam integration."""

from datetime import timedelta

DOMAIN = "dang_kiem_viet_nam"
PLATFORMS = ["sensor"]
UPDATE_INTERVAL = timedelta(hours=12)

CONF_BIENDANGKY = "biendangky"
CONF_SOKHUNG = "sokhung"
CONF_LOAIPT = "loaipt"

DEFAULT_LOAIPT = "1"
