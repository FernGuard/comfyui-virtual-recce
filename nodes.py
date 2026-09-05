"""
Virtual Recce — custom ComfyUI nodes for data-grounded location scouting.

Turns a real address into a real reference plate (Google Street View), grounded
in the REAL sun position and REAL weather for a given date/time, then builds a
generation prompt so you can dress the location with your set and characters in
the correct light.

Node chain:
  Geocode Address -> Street View Reference -> (Sun Position + Weather)
                  -> Recce Prompt Builder -> [your img2img/ControlNet]

External services (bring your own keys):
  - Google Maps Platform (Geocoding + Street View Static + metadata)
  - Open-Meteo (weather, free, no key)

pip deps: requests, astral, timezonefinder   (numpy/torch/Pillow ship with ComfyUI)
"""

import io
import math
import datetime as _dt

import numpy as np
import torch
from PIL import Image


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _require(mod_name, pip_name=None):
    try:
        return __import__(mod_name)
    except ImportError as e:
        raise RuntimeError(
            f"Virtual Recce needs the '{pip_name or mod_name}' package. "
            f"Install with:  pip install {pip_name or mod_name}"
        ) from e


def _pil_to_tensor(img: Image.Image) -> torch.Tensor:
    """PIL -> ComfyUI IMAGE tensor (1, H, W, 3) float32 in 0..1."""
    img = img.convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _blank_tensor(w=640, h=640):
    arr = np.zeros((h, w, 3), dtype=np.float32)
    return torch.from_numpy(arr)[None, ...]


_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass(azimuth: float) -> str:
    return _COMPASS[int(round((azimuth % 360) / 22.5)) % 16]


def _now_local(tz):
    return _dt.datetime.now(tz)


# --------------------------------------------------------------------------- #
# 1. Geocode Address
# --------------------------------------------------------------------------- #

class VRGeocodeAddress:
    """Address -> latitude, longitude (Google Geocoding API)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "address": ("STRING", {"default": "Griffith Observatory, Los Angeles, CA"}),
            "google_api_key": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("FLOAT", "FLOAT", "STRING")
    RETURN_NAMES = ("latitude", "longitude", "formatted_address")
    FUNCTION = "geocode"
    CATEGORY = "Virtual Recce"

    def geocode(self, address, google_api_key):
        requests = _require("requests")
        if not google_api_key.strip():
            raise RuntimeError(
                "Geocode: paste a Google Maps API key (Geocoding API enabled). "
                "Create one: https://console.cloud.google.com/apis/credentials"
            )
        r = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": google_api_key.strip()},
            timeout=30,
        )
        data = r.json()
        if data.get("status") != "OK" or not data.get("results"):
            raise RuntimeError(f"Geocode failed: {data.get('status')} "
                               f"{data.get('error_message', '')}".strip())
        top = data["results"][0]
        loc = top["geometry"]["location"]
        return (float(loc["lat"]), float(loc["lng"]), top.get("formatted_address", address))


# --------------------------------------------------------------------------- #
# 2. Street View Reference
# --------------------------------------------------------------------------- #

class VRStreetViewReference:
    """lat/long + camera -> real street-level reference IMAGE (Street View Static API)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latitude": ("FLOAT", {"default": 34.1184, "min": -90.0, "max": 90.0, "step": 0.000001}),
            "longitude": ("FLOAT", {"default": -118.3004, "min": -180.0, "max": 180.0, "step": 0.000001}),
            "heading": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 360.0, "step": 1.0}),
            "pitch": ("FLOAT", {"default": 0.0, "min": -90.0, "max": 90.0, "step": 1.0}),
            "fov": ("FLOAT", {"default": 90.0, "min": 10.0, "max": 120.0, "step": 1.0}),
            "width": ("INT", {"default": 640, "min": 16, "max": 640, "step": 16}),
            "height": ("INT", {"default": 640, "min": 16, "max": 640, "step": 16}),
            "google_api_key": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("reference_image", "status")
    FUNCTION = "fetch"
    CATEGORY = "Virtual Recce"

    def fetch(self, latitude, longitude, heading, pitch, fov, width, height, google_api_key):
        requests = _require("requests")
        if not google_api_key.strip():
            raise RuntimeError(
                "Street View: paste a Google Maps API key (Street View Static API enabled). "
                "Create one: https://console.cloud.google.com/apis/credentials"
            )
        loc = f"{latitude},{longitude}"
        key = google_api_key.strip()

        # metadata check first (free) — avoids paying for a grey "no imagery" tile
        meta = requests.get(
            "https://maps.googleapis.com/maps/api/streetview/metadata",
            params={"location": loc, "key": key}, timeout=30,
        ).json()
        if meta.get("status") != "OK":
            return (_blank_tensor(width, height),
                    f"No Street View imagery at this location (status: {meta.get('status')}).")

        r = requests.get(
            "https://maps.googleapis.com/maps/api/streetview",
            params={"location": loc, "size": f"{width}x{height}", "heading": heading,
                    "pitch": pitch, "fov": fov, "key": key, "return_error_code": "true"},
            timeout=60,
        )
        if r.status_code != 200 or "image" not in r.headers.get("Content-Type", ""):
            raise RuntimeError(f"Street View fetch failed ({r.status_code}): {r.text[:200]}")
        img = Image.open(io.BytesIO(r.content))
        date = meta.get("date", "unknown")
        return (_pil_to_tensor(img),
                f"OK — imagery {date}, heading {heading:.0f}° ({_compass(heading)}).")


# --------------------------------------------------------------------------- #
# 3. Sun Position (the real-data lighting brain)
# --------------------------------------------------------------------------- #

class VRSunPosition:
    """lat/long + date/time -> real sun azimuth/elevation + a light description for prompting."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latitude": ("FLOAT", {"default": 34.1184, "min": -90.0, "max": 90.0, "step": 0.000001}),
            "longitude": ("FLOAT", {"default": -118.3004, "min": -180.0, "max": 180.0, "step": 0.000001}),
            "date": ("STRING", {"default": "2026-10-03", "tooltip": "YYYY-MM-DD, or blank = today"}),
            "time": ("STRING", {"default": "17:30", "tooltip": "HH:MM 24h local, or blank = now"}),
            "timezone": ("STRING", {"default": "auto", "tooltip": "'auto' resolves from lat/long"}),
        }}

    RETURN_TYPES = ("FLOAT", "FLOAT", "STRING", "STRING")
    RETURN_NAMES = ("azimuth", "elevation", "phase", "light_description")
    FUNCTION = "compute"
    CATEGORY = "Virtual Recce"

    def _tz(self, latitude, longitude, timezone):
        from zoneinfo import ZoneInfo
        if timezone.strip().lower() == "auto":
            _require("timezonefinder")
            from timezonefinder import TimezoneFinder
            name = TimezoneFinder().timezone_at(lat=latitude, lng=longitude) or "UTC"
        else:
            name = timezone.strip()
        return ZoneInfo(name), name

    def compute(self, latitude, longitude, date, time, timezone):
        _require("astral")
        from astral import Observer
        from astral.sun import azimuth as _az, elevation as _el

        tz, tz_name = self._tz(latitude, longitude, timezone)
        now = _now_local(tz)
        y, m, d = (now.year, now.month, now.day)
        if date.strip():
            y, m, d = [int(x) for x in date.strip().split("-")]
        hh, mm = (now.hour, now.minute)
        if time.strip():
            hh, mm = [int(x) for x in time.strip().split(":")]
        when = _dt.datetime(y, m, d, hh, mm, tzinfo=tz)

        obs = Observer(latitude=latitude, longitude=longitude)
        az = float(_az(obs, when))
        el = float(_el(obs, when))

        if el < -6:
            phase = "night"
            note = "no direct sun; ambient / practical lighting only."
        elif el < -0.833:
            phase = "blue hour"
            note = ("cool blue twilight, soft diffuse ambient light, "
                    "no direct sun, deep shadows filled by sky.")
        elif el < 6:
            phase = "golden hour"
            note = (f"low warm golden sunlight from the {_compass(az)}, "
                    f"very long shadows raking across the scene.")
        elif el < 20:
            phase = "low sun"
            note = (f"warm directional sunlight from the {_compass(az)}, "
                    f"long soft shadows, gentle contrast.")
        elif el < 50:
            phase = "daylight"
            note = (f"neutral daylight from the {_compass(az)}, "
                    f"medium shadows, clean contrast.")
        else:
            phase = "harsh midday"
            note = "steep overhead sun, short hard shadows, high contrast."

        light = (f"{phase}: sun to the {_compass(az)} at {az:.0f}deg azimuth, "
                 f"{el:.0f}deg elevation ({tz_name}, {when:%Y-%m-%d %H:%M}). {note}")
        return (az, el, phase, light)


# --------------------------------------------------------------------------- #
# 4. Location Weather
# --------------------------------------------------------------------------- #

_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog", 51: "light drizzle", 53: "drizzle",
    55: "dense drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "violent rain showers", 95: "thunderstorm",
    96: "thunderstorm w/ hail", 99: "thunderstorm w/ heavy hail",
}


class VRLocationWeather:
    """lat/long + date/time -> real weather description (Open-Meteo, free, no key)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latitude": ("FLOAT", {"default": 34.1184, "min": -90.0, "max": 90.0, "step": 0.000001}),
            "longitude": ("FLOAT", {"default": -118.3004, "min": -180.0, "max": 180.0, "step": 0.000001}),
            "date": ("STRING", {"default": "2026-10-03"}),
            "time": ("STRING", {"default": "17:30"}),
        }}

    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("weather_description", "cloud_cover_pct")
    FUNCTION = "fetch"
    CATEGORY = "Virtual Recce"

    def fetch(self, latitude, longitude, date, time):
        requests = _require("requests")
        try:
            hour = int(time.strip().split(":")[0]) if time.strip() else 12
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": latitude, "longitude": longitude,
                        "hourly": "cloud_cover,weather_code",
                        "start_date": date.strip(), "end_date": date.strip(),
                        "timezone": "auto"},
                timeout=30,
            ).json()
            hourly = r.get("hourly", {})
            codes = hourly.get("weather_code", [])
            clouds = hourly.get("cloud_cover", [])
            if not codes:
                return ("weather unavailable for this date (outside forecast range).", 0.0)
            idx = min(hour, len(codes) - 1)
            code = codes[idx]
            cloud = float(clouds[idx]) if idx < len(clouds) else 0.0
            desc = _WMO.get(code, "unknown conditions")
            return (f"{desc}, {cloud:.0f}% cloud cover.", cloud)
        except Exception as e:  # noqa
            return (f"weather unavailable ({e}).", 0.0)


# --------------------------------------------------------------------------- #
# 5. Recce Prompt Builder
# --------------------------------------------------------------------------- #

class VRReccePromptBuilder:
    """Combine location + set + character + real light + weather into one prompt."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "set_description": ("STRING", {"multiline": True,
                "default": "dressed as a 1970s film set, period vehicles, film crew equipment"}),
            "character_description": ("STRING", {"multiline": True,
                "default": "a lone detective in a tan trench coat standing center frame"}),
            "light_description": ("STRING", {"forceInput": True}),
        }, "optional": {
            "weather_description": ("STRING", {"forceInput": True}),
            "camera_and_style": ("STRING", {"multiline": True,
                "default": "cinematic, anamorphic, shallow depth of field, film grain"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "Virtual Recce"

    def build(self, set_description, character_description, light_description,
              weather_description="", camera_and_style=""):
        parts = [
            character_description.strip(),
            "at this real location," ,
            set_description.strip() + ".",
            f"Lighting: {light_description.strip()}",
        ]
        if weather_description.strip():
            parts.append(f"Weather: {weather_description.strip()}")
        if camera_and_style.strip():
            parts.append(camera_and_style.strip())
        prompt = " ".join(p for p in parts if p).replace("  ", " ")
        return (prompt,)


# --------------------------------------------------------------------------- #
# 6. Google Maps API Key (single source -> fan out to every node that needs it)
# --------------------------------------------------------------------------- #

class VRGoogleMapsKey:
    """Hold ONE Google Maps Platform key and fan it out.

    Wire the output into the `google_api_key` input of Geocode Address and
    Street View Reference so you paste the key only once. The key needs the
    Geocoding API and Street View Static API enabled.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "google_api_key": ("STRING", {
                "default": "",
                "multiline": False,
                "tooltip": ("One Maps key with Geocoding + Street View Static "
                            "enabled. Wire the output into every node's "
                            "google_api_key input."),
            }),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("google_api_key",)
    FUNCTION = "provide"
    CATEGORY = "Virtual Recce"

    def provide(self, google_api_key):
        return (google_api_key.strip(),)


# --------------------------------------------------------------------------- #
# registration
# --------------------------------------------------------------------------- #

NODE_CLASS_MAPPINGS = {
    "VRGoogleMapsKey": VRGoogleMapsKey,
    "VRGeocodeAddress": VRGeocodeAddress,
    "VRStreetViewReference": VRStreetViewReference,
    "VRSunPosition": VRSunPosition,
    "VRLocationWeather": VRLocationWeather,
    "VRReccePromptBuilder": VRReccePromptBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGoogleMapsKey": "Recce · Google Maps Key",
    "VRGeocodeAddress": "Recce · Geocode Address",
    "VRStreetViewReference": "Recce · Street View Reference",
    "VRSunPosition": "Recce · Sun Position (real light)",
    "VRLocationWeather": "Recce · Location Weather",
    "VRReccePromptBuilder": "Recce · Prompt Builder",
}
