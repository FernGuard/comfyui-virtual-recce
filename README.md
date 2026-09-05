# Virtual Recce — data-grounded location scouting for ComfyUI

A small pack of custom ComfyUI nodes that turn a **real address** into a **real
reference plate**, grounded in the **real sun position** and **real weather** for
a chosen date and time — so a director can scout, dress, and *light* a scene from
their desk before spending a dollar on travel.

Most AI-video demos hallucinate a pretty frame. This one is built the way a
production actually works: real location, real sun angle, real conditions, then
generation on top. The lighting is driven by an actual solar-position
calculation for that lat/long and moment — the detail a cinematographer trusts.

```
Geocode Address ─▶ Street View Reference ─┐
                                          ├─▶ Recce Prompt Builder ─▶ [your img2img / ControlNet] ─▶ dressed plate
Sun Position (real light) ────────────────┤
Location Weather ─────────────────────────┘
```

## Why it exists

Location scouting is slow and expensive — travel, permits, weather roulette — and
DPs plan shoot days around **sun position** ("golden hour, sun camera-left"). A
virtual recce grounded in real geography, sun, and weather is a genuine planning
instrument, not a toy.

## Install

Python 3.10+ and a working [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
install. The data nodes (geocode, sun, weather) need no GPU. Only the "dress the
plate" image step uses a model.

### ComfyUI Manager

1. **ComfyUI Manager → Custom Nodes Manager → Install via Git URL**
2. Paste: `https://github.com/FernGuard/comfyui-virtual-recce`
3. Restart when prompted. Nodes appear under **Virtual Recce**.

### Manual

```sh
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/FernGuard/comfyui-virtual-recce.git
# Desktop app Python, or your ComfyUI venv:
/path/to/ComfyUI/.venv/bin/python -m pip install -r comfyui-virtual-recce/requirements.txt
```

Restart ComfyUI. Right-click → Add Node → **Virtual Recce**.

## Keys you must bring

This pack ships **no credentials**. Paste keys into the node widgets. Do not put
them in git, issues, or saved workflow files you commit. This pack does **not**
load a `.env` file.

| Provider | Widget | Used for | Create your key |
|---|---|---|---|
| Google Maps Platform | `google_api_key` | Geocoding + Street View | https://console.cloud.google.com/apis/credentials |

Enable **Geocoding API** and **Street View Static API** on the Google key.
Open-Meteo weather is free and needs no key.

A missing required key raises a clear error naming the node. It does not
silently skip the paid call.

Wire **Recce · Google Maps Key** once and fan the output into Geocode / Street
View so you paste the Maps key only once.

## Nodes

| Node | In → Out | Notes |
|---|---|---|
| **Geocode Address** | address → lat, long, formatted_address | Google Geocoding |
| **Street View Reference** | lat/long + heading/pitch/fov → IMAGE | real plate; metadata check first so you don't pay for "no imagery" |
| **Sun Position (real light)** | lat/long + date/time → azimuth, elevation, phase, **light_description** | `timezone: auto` resolves from coordinates |
| **Location Weather** | lat/long + date/time → weather_description, cloud % | Open-Meteo |
| **Prompt Builder** | set + character + light + weather → prompt | wire `light_description` / `weather_description` in |
| **Google Maps Key** | key → key | paste once, fan out |

## Example flow

1. **Geocode Address** → e.g. a public landmark you are allowed to reference.
2. Feed lat/long into **Street View Reference** (`heading` = camera direction) → real plate.
3. Feed the same lat/long + your `date`/`time` into **Sun Position** and **Location Weather**.
4. **Prompt Builder**: your set + character, plus `light_description` and `weather_description`.
5. Dress the plate with any img2img / ControlNet subgraph (Street View image as init).

## Honest caveats

- **Street View Static** tops out at 640×640 per tile on the standard tier.
- **Weather** uses the Open-Meteo forecast window; historical dates need the archive API.
- **v2 idea:** Photorealistic 3D Tiles for camera angles Street View never drove.

You are responsible for Maps / Street View terms, location rights, and
anything you generate from the plates.

## License

[MIT](LICENSE). You may use, copy, modify, and distribute this pack under the
license terms. See [SECURITY.md](SECURITY.md).
