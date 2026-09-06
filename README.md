# Virtual Recce — data-grounded location scouting for ComfyUI

A pack of custom ComfyUI nodes that turn a **real address** into a **real
reference plate**, grounded in the **real sun position** and **real weather** for
a chosen date and time — so a director can scout, dress, and *light* a scene from
their desk before spending a dollar on travel.

Most AI-video demos hallucinate a pretty frame. This one is built the way a
production actually works: real location, real sun angle, real conditions, then
generation on top. The lighting is driven by an actual solar-position
calculation for that lat/long and moment — the detail a cinematographer trusts.

```
Location Picker / Geocode ─▶ Street View Reference ─┐
                                                    ├─▶ Set & Cast ─▶ Prompt Builder ─▶ [your img2img]
Sun Position (real light) ──────────────────────────┤
Location Weather / Shoot Time ──────────────────────┘
```

## Why it exists

Location scouting is slow and expensive — travel, permits, weather roulette — and
DPs plan shoot days around **sun position** ("golden hour, sun camera-left"). A
virtual recce grounded in real geography, sun, and weather is a genuine planning
instrument, not a toy.

## Install

Python 3.10+ and a working [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
install. The data nodes (geocode, sun, weather) need no GPU. Dressing the plate
uses whatever image model you already run in ComfyUI.

### ComfyUI Manager

1. **ComfyUI Manager → Custom Nodes Manager → Install via Git URL**
2. Paste: `https://github.com/FernGuard/comfyui-virtual-recce`
3. Restart when prompted. Nodes appear under **Virtual Recce**.

### Manual

```sh
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/FernGuard/comfyui-virtual-recce.git
/path/to/ComfyUI/.venv/bin/python -m pip install -r comfyui-virtual-recce/requirements.txt
```

Restart ComfyUI. Right-click → Add Node → **Virtual Recce**.

Copy `examples/*.png` into your ComfyUI `input/` folder so the example
workflows can Load Image by filename.

## Keys you must bring

This pack ships **no credentials**. Paste a Google Maps key into **Recce · Google
Maps Key** (or each node's `google_api_key` widget). Do not put keys in git,
issues, or saved workflow files you commit. This pack does **not** load a `.env`
file.

| Provider | Widget | Used for | Create your key |
|---|---|---|---|
| Google Maps Platform | `google_api_key` | Geocoding + Street View | https://console.cloud.google.com/apis/credentials |

Enable **Geocoding API** and **Street View Static API** on the Google key.
Open-Meteo weather is free and needs no key.

A missing required key raises a clear error naming the node and the signup URL.
It does not silently skip the paid call.

Some example graphs also use ComfyUI Gemini / image-model nodes. Those are
**not** this pack. Install your usual partner nodes if you want those graphs to
generate; or swap in any img2img subgraph.

## Nodes

| Node | In → Out | Notes |
|---|---|---|
| **Google Maps Key** | key → key | paste once, fan out |
| **Location Picker (Globe)** | address or click → lat, long, formatted_address | interactive globe in `web/` |
| **Geocode Address** | address → lat, long, formatted_address | Google Geocoding |
| **Street View Reference** | lat/long + heading/pitch/fov → IMAGE | metadata check first so you don't pay for "no imagery" |
| **Shoot Time** | date/time → date, time | keep Sun and Weather on the same moment; blank date = today |
| **Sun Position (real light)** | lat/long + date/time → azimuth, elevation, phase, **light_description** | `timezone: auto` resolves from coordinates |
| **Location Weather** | lat/long + date/time → weather_description, cloud % | Open-Meteo; blank date = today |
| **Set & Cast** | plate + set + actors → image batch + notes | for a multi-reference image model |
| **Prompt Builder** | light + weather + location + notes → prompt | labeled brief |

## Example workflows

See [workflows/README.md](workflows/README.md). Open from ComfyUI or drag the JSON
onto the canvas.

| File | Maps key | What it does |
|---|---|---|
| `workflows/dryrun_keyless.json` | No | Sun + weather + prompt |
| `workflows/step2_full_nanobanana.json` | Yes | Recce + dress the Street View plate |
| `workflows/step2_full_nanobanana_UI.json` | Yes | Same graph in UI format |
| `workflows/step2_v2_globe_setcast.json` | Yes | Globe picker + Set & Cast |
| `workflows/step2_v3_story.json` | Yes | Shoot Time + story brief + dress |
| `workflows/gen_references.json` | No | Batch the example reference stills |

Testing stills live in [examples/](examples/). Copy them into ComfyUI `input/`
before graphs that Load Image.

## Honest caveats

- **Street View Static** tops out at 640×640 per tile on the standard tier.
- **Weather** uses the Open-Meteo forecast window; historical dates need the archive API.
- The globe widget loads `globe.gl` from a CDN; lat/long widgets still work offline.
- **v2 idea:** Photorealistic 3D Tiles for camera angles Street View never drove.

You are responsible for Maps / Street View terms, location rights, partner-node
terms, and anything you generate from the plates.

## License

[MIT](LICENSE). You may use, copy, modify, and distribute this pack under the
license terms. See [SECURITY.md](SECURITY.md).
