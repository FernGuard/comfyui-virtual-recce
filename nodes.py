"""
Virtual Recce - custom ComfyUI nodes for data-grounded location scouting.

Turns a real address into a real reference plate (Google Street View), grounded
in the REAL sun position and REAL weather for a given date/time, then builds a
generation prompt so you can dress the location with your set and characters in
the correct light.

Node chain:
  Location Picker / Geocode -> Street View Reference -> (Sun Position + Weather)
                  -> Set & Cast -> Recce Prompt Builder -> [your img2img]

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


def _safe_get(requests, url, params, timeout, label):
    """Run a GET without allowing credential-bearing URLs into tracebacks."""
    try:
        return requests.get(url, params=params, timeout=timeout)
    except Exception as exc:
        raise RuntimeError(
            f"{label}: request failed ({type(exc).__name__}). "
            "Check network access and provider status."
        ) from None


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
        r = _safe_get(
            requests,
            "https://maps.googleapis.com/maps/api/geocode/json",
            {"address": address, "key": google_api_key.strip()},
            30,
            "Geocode",
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError("Geocode: provider returned an invalid response.") from None
        if data.get("status") != "OK" or not data.get("results"):
            raise RuntimeError(
                f"Geocode failed: {data.get('status', 'UNKNOWN')}. "
                "Check billing, API enablement, key restrictions, and the address."
            )
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

        # metadata check first (free) - avoids paying for a grey "no imagery" tile
        meta_response = _safe_get(
            requests,
            "https://maps.googleapis.com/maps/api/streetview/metadata",
            {"location": loc, "key": key},
            30,
            "Street View metadata",
        )
        try:
            meta = meta_response.json()
        except Exception:
            raise RuntimeError("Street View metadata: provider returned an invalid response.") from None
        if meta.get("status") != "OK":
            return (_blank_tensor(width, height),
                    f"No Street View imagery at this location (status: {meta.get('status')}).")

        r = _safe_get(
            requests,
            "https://maps.googleapis.com/maps/api/streetview",
            {"location": loc, "size": f"{width}x{height}", "heading": heading,
             "pitch": pitch, "fov": fov, "key": key, "return_error_code": "true"},
            60,
            "Street View image",
        )
        if r.status_code != 200 or "image" not in r.headers.get("Content-Type", ""):
            raise RuntimeError(f"Street View fetch failed (HTTP {r.status_code}).")
        img = Image.open(io.BytesIO(r.content))
        date = meta.get("date", "unknown")
        return (_pil_to_tensor(img),
                f"OK - imagery {date}, heading {heading:.0f}° ({_compass(heading)}).")


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
            "date": ("STRING", {"default": "", "tooltip": "YYYY-MM-DD, or blank = today"}),
            "time": ("STRING", {"default": "17:30", "tooltip": "HH:MM 24h, or blank = 12:00 if used without Shoot Time"}),
        }}

    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("weather_description", "cloud_cover_pct")
    FUNCTION = "fetch"
    CATEGORY = "Virtual Recce"

    def fetch(self, latitude, longitude, date, time):
        requests = _require("requests")
        try:
            day = date.strip() or _dt.date.today().isoformat()
            hour = int(time.strip().split(":")[0]) if time.strip() else 12
            r = _safe_get(
                requests,
                "https://api.open-meteo.com/v1/forecast",
                {"latitude": latitude, "longitude": longitude,
                 "hourly": "cloud_cover,weather_code",
                 "start_date": day, "end_date": day,
                 "timezone": "auto"},
                30,
                "Weather",
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
    """Gather the grounded facts (location, real light, real weather, set, cast,
    references) into ONE clearly-labeled brief.

    Feed this brief straight into an image model, or send it first to a text LLM
    (e.g. the Google Gemini node) with a 'write a short cinematic scene' system
    prompt. Then send the LLM's story to the image model. The labeled sections
    are designed to be easy for an LLM to turn into a story while keeping every
    concrete visual fact.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "light_description": ("STRING", {"forceInput": True}),
        }, "optional": {
            "location": ("STRING", {"forceInput": True}),
            "weather_description": ("STRING", {"forceInput": True}),
            "reference_notes": ("STRING", {"forceInput": True}),
            "set_description": ("STRING", {"multiline": True, "default": ""}),
            "character_description": ("STRING", {"multiline": True, "default": ""}),
            "direction": ("STRING", {"multiline": True, "default": "",
                "tooltip": ("Optional genre / tone / beat to steer the story "
                            "(e.g. 'fantasy last stand', 'noir stakeout'). The CAST "
                            "comes from the Set & Cast node's actor names. Leave this "
                            "blank to let the story emerge from the references + real data.")}),
            "camera_and_style": ("STRING", {"multiline": True,
                "default": "cinematic, anamorphic, shallow depth of field, film grain"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "Virtual Recce"

    def build(self, light_description, location="", weather_description="",
              reference_notes="", set_description="", character_description="",
              direction="", camera_and_style=""):
        lines = []
        if location.strip():
            lines.append(f"LOCATION: {location.strip()}")
        if direction.strip():
            lines.append(f"DIRECTION / GENRE: {direction.strip()}")
        if character_description.strip():
            lines.append(f"CHARACTER: {character_description.strip()}")
        if set_description.strip():
            lines.append(f"SET: {set_description.strip()}")
        if light_description.strip():
            lines.append(f"REAL LIGHT: {light_description.strip()}")
        if weather_description.strip():
            lines.append(f"REAL WEATHER: {weather_description.strip()}")
        if reference_notes.strip():
            lines.append(f"CAST & SET (reference images): {reference_notes.strip()}")
        if camera_and_style.strip():
            lines.append(f"STYLE: {camera_and_style.strip()}")
        return ("\n".join(lines),)


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
                "password": True,
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
# 7b. Shoot Time (one date/time -> fan out to Sun Position + Weather)
# --------------------------------------------------------------------------- #

class VRShootTime:
    """One shoot date/time, fanned out to Sun Position and Weather so the two
    never drift apart. Wire both outputs into each node's date/time inputs.

    Blank date and time are resolved once from the ComfyUI host clock. This keeps
    Weather and Sun Position on the same explicit values. For a remote location,
    enter the destination's date explicitly if it differs from the host date.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "date": ("STRING", {"default": "", "tooltip": (
                "YYYY-MM-DD, or blank = the ComfyUI host's current date. For REAL "
                "weather, use a date within ~16 days (Open-Meteo forecast range).")}),
            "time": ("STRING", {"default": "17:30", "tooltip": (
                "HH:MM 24h local, or blank = the ComfyUI host's current time.")}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("date", "time")
    FUNCTION = "provide"
    CATEGORY = "Virtual Recce"

    def provide(self, date, time):
        now = _dt.datetime.now().astimezone()
        resolved_date = date.strip() or now.date().isoformat()
        resolved_time = time.strip() or now.strftime("%H:%M")
        return (resolved_date, resolved_time)


# --------------------------------------------------------------------------- #
# 8. Location Picker (3D globe) - address <-> coordinates, whichever you set
# --------------------------------------------------------------------------- #

class VRLocationPicker:
    """Pick a location by ADDRESS or by clicking the 3D globe; output coords + address.

    Whichever you set drives (input_mode):
      - 'auto'        : if `address` is non-empty -> geocode it; else use lat/long.
      - 'address'     : always geocode `address`.
      - 'coordinates' : always use lat/long, reverse-geocode to a formatted address.

    The globe (a frontend widget shipped in ./web) keeps its marker and the
    latitude/longitude widgets in sync live: drag to spin, click to drop a point.
    Clicking the globe switches `input_mode` to `coordinates` so the clicked
    point wins without deleting the saved address.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "address": ("STRING", {"default": "Griffith Observatory, Los Angeles, CA"}),
            "latitude": ("FLOAT", {"default": 34.1184, "min": -90.0, "max": 90.0, "step": 0.000001}),
            "longitude": ("FLOAT", {"default": -118.3004, "min": -180.0, "max": 180.0, "step": 0.000001}),
            "input_mode": (["auto", "address", "coordinates"], {"default": "auto"}),
            "google_api_key": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("FLOAT", "FLOAT", "STRING")
    RETURN_NAMES = ("latitude", "longitude", "formatted_address")
    FUNCTION = "resolve"
    CATEGORY = "Virtual Recce"

    def resolve(self, address, latitude, longitude, input_mode, google_api_key):
        requests = _require("requests")
        key = google_api_key.strip()
        use_address = (input_mode == "address") or (input_mode == "auto" and address.strip())

        if use_address:
            if not key:
                raise RuntimeError(
                    "Location Picker: paste a Google Maps API key (Geocoding API enabled). "
                    "Create one: https://console.cloud.google.com/apis/credentials"
                )
            response = _safe_get(
                requests,
                "https://maps.googleapis.com/maps/api/geocode/json",
                {"address": address, "key": key},
                30,
                "Location Picker",
            )
            try:
                r = response.json()
            except Exception:
                raise RuntimeError("Location Picker: provider returned an invalid response.") from None
            if r.get("status") != "OK" or not r.get("results"):
                raise RuntimeError(
                    f"Location Picker geocode failed: {r.get('status', 'UNKNOWN')}. "
                    "Check billing, API enablement, key restrictions, and the address."
                )
            top = r["results"][0]
            loc = top["geometry"]["location"]
            return (float(loc["lat"]), float(loc["lng"]), top.get("formatted_address", address))

        # coordinates drive; best-effort reverse geocode for a human-readable address
        formatted = f"{latitude:.6f}, {longitude:.6f}"
        if key:
            try:
                response = _safe_get(
                    requests,
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    {"latlng": f"{latitude},{longitude}", "key": key},
                    30,
                    "Location Picker reverse geocode",
                )
                r = response.json()
                if r.get("status") == "OK" and r.get("results"):
                    formatted = r["results"][0].get("formatted_address", formatted)
            except Exception:  # noqa
                pass
        return (float(latitude), float(longitude), formatted)


# --------------------------------------------------------------------------- #
# 9. Set & Cast - bundle plate + set-dressing + actor refs for a multi-image model
# --------------------------------------------------------------------------- #

class VRSetAndCast:
    """Bundle the location plate + set-dressing + up to two actor references into
    ONE image batch for a multi-reference image model (e.g. Nano Banana Pro),
    plus a prompt fragment that labels each reference so the model composites them.

    Wire `reference_images` into the model's image input and `reference_notes`
    into the Prompt Builder's `reference_notes` input.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "resolution": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64,
                "tooltip": "All references are resized to this square size before batching."}),
        }, "optional": {
            "plate": ("IMAGE",),
            "background_set": ("IMAGE",),
            "actor_1": ("IMAGE",),
            "actor_1_name": ("STRING", {"default": "the lead detective"}),
            "actor_2": ("IMAGE",),
            "actor_2_name": ("STRING", {"default": "the second lead"}),
        }}

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("reference_images", "reference_notes")
    FUNCTION = "bundle"
    CATEGORY = "Virtual Recce"

    def _square(self, img, res):
        import torch.nn.functional as F
        x = img[0:1].permute(0, 3, 1, 2)  # 1,C,H,W
        x = F.interpolate(x, size=(res, res), mode="bilinear", align_corners=False)
        return x.permute(0, 2, 3, 1).clamp(0.0, 1.0)

    def bundle(self, resolution, plate=None, background_set=None,
               actor_1=None, actor_1_name="the lead detective",
               actor_2=None, actor_2_name="the second lead"):
        items, notes, idx = [], [], 1

        def add(img, label):
            nonlocal idx
            if img is None:
                return
            items.append(self._square(img, resolution))
            notes.append(f"image {idx} = {label}")
            idx += 1

        add(plate, "the REAL location plate: preserve its architecture, layout, "
                   "horizon and camera perspective")
        add(background_set, "set-dressing reference: apply this styling and props to the location")
        add(actor_1, f"{actor_1_name.strip() or 'the first actor'}: place this person into the scene")
        add(actor_2, f"{actor_2_name.strip() or 'the second actor'}: place this person into the scene")

        if not items:
            raise RuntimeError("Set & Cast: connect at least one image (plate / background / actor).")

        batch = torch.cat(items, dim=0)
        note = ("Reference images, in order: " + "; ".join(notes) + ". "
                "Composite the actors and set dressing INTO the real location plate, "
                "keeping the plate's architecture, layout and camera perspective intact.")
        return (batch, note)


# --------------------------------------------------------------------------- #
# registration
# --------------------------------------------------------------------------- #

NODE_CLASS_MAPPINGS = {
    "VRGoogleMapsKey": VRGoogleMapsKey,
    "VRShootTime": VRShootTime,
    "VRLocationPicker": VRLocationPicker,
    "VRSetAndCast": VRSetAndCast,
    "VRGeocodeAddress": VRGeocodeAddress,
    "VRStreetViewReference": VRStreetViewReference,
    "VRSunPosition": VRSunPosition,
    "VRLocationWeather": VRLocationWeather,
    "VRReccePromptBuilder": VRReccePromptBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGoogleMapsKey": "Recce · Google Maps Key",
    "VRShootTime": "Recce · Shoot Time",
    "VRLocationPicker": "Recce · Location Picker (Globe)",
    "VRSetAndCast": "Recce · Set & Cast",
    "VRGeocodeAddress": "Recce · Geocode Address",
    "VRStreetViewReference": "Recce · Street View Reference",
    "VRSunPosition": "Recce · Sun Position (real light)",
    "VRLocationWeather": "Recce · Location Weather",
    "VRReccePromptBuilder": "Recce · Prompt Builder",
}
