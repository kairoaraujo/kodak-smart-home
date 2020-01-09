"""This component provides support to the Kodak Smart Home camera."""
import asyncio
from datetime import timedelta
import logging

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from . import (
    ATTRIBUTION,
    DATA_KODAKSMARTHOME_CAMS,
    NOTIFICATION_ID,
    SIGNAL_UPDATE_KODAKSMARTHOME,
)

CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"

FORCE_REFRESH_INTERVAL = timedelta(minutes=45)

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_TITLE = "Kodak Smart Home Camera Setup"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Kodak Smart Home Camera."""
    kodak_smart_home_cams = hass.data[DATA_KODAKSMARTHOME_CAMS]
    kodak_smart_home_cams.connect()

    cams = []
    cam_offline = []
    for camera in kodak_smart_home_cams.get_devices:
        if camera["is_online"]:
            cams.append(
                KodakSmartHomeCam(
                    hass,
                    camera,
                    kodak_smart_home_cams.get_motion_events(
                        device_id=camera["device_id"]
                    ),
                    config,
                )
            )
        else:
            cam_offline.append(camera)

    # show notification for all cameras offline
    if cam_offline:
        cameras = str(", ".join([camera["name"] for camera in cam_offline]))

        err_msg = (
            """Cameras are offline""" """ following cameras: {}.""".format(
                cameras
            )
        )

        _LOGGER.error(err_msg)
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "It needs to be fixed in the Camera/Kodak Smart Home Portal. "
            "Home Assistant reboot is required."
            "".format(err_msg),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )

    add_entities(cams, True)
    return True


class KodakSmartHomeCam(Camera):
    """An implementation of a Kodak Smart Home camera."""

    def __init__(self, hass, camera, motion_events, device_info):
        """Initialize Kodak Smart Home camera."""
        super().__init__()
        self._camera = camera
        self._motion_events = motion_events
        self._hass = hass
        self._name = self._camera["name"]
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)

        if len(self._motion_events) > 0:
            self._last_video_id = self._motion_events[0]["id"]
        else:
            self._last_video_id = None

        if self._last_video_id is not None:
            for event_data in self._motion_events[0]["data"]:
                # type 2 is video url
                if "file_type" in event_data and event_data["file_type"] == 2:
                    self._video_url = event_data["file"]
        else:
            self._video_url = None

        self._utcnow = dt_util.utcnow()
        self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_KODAKSMARTHOME, self._update_callback
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
        _LOGGER.debug(
            "Updating Kodak Smart Home camera %s (callback)", self.name
        )

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._camera["device_id"]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._camera["device_id"],
            "firmware": self._camera["firmware"]["version"],
            "timezone": self._camera["zone_id"],
            "video_url": self._video_url,
            "last_video_id": self._last_video_id,
        }

    async def async_camera_image(self):
        """Return a still image response from the camera."""

        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        if self._video_url is None:
            return

        image = await asyncio.shield(
            ffmpeg.get_image(
                self._video_url,
                output_format=IMAGE_JPEG,
                extra_cmd=self._ffmpeg_arguments,
            )
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""

        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(self._video_url, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    def update(self):
        """Update camera entity and refresh attributes."""
        _LOGGER.debug("Checking if Kodak Camera needs to refresh video_url")

        self._utcnow = dt_util.utcnow()

        if len(self._motion_events) > 0:
            last_event = self._motion_events[0]["id"]

        else:
            return

        if (
            self._last_video_id != last_event or
            self._utcnow >= self._expires_at
        ):

            video_url = self._video_url
            if video_url:
                _LOGGER.info("Kodak Smart Home camera properties refreshed")

                # update attributes if new video or if URL has expired
                self._last_video_id = last_event
                self._video_url = video_url
                self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow
