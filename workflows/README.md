# Example workflows

Load from ComfyUI: **Workflow → Open**, or drag the JSON onto the canvas.

Paste your Google Maps key only into **Recce · Google Maps Key** (or the
`google_api_key` widget). Do not commit a filled key.

Copy `examples/*.png` into ComfyUI `input/` before graphs that Load Image.

| File | Maps key | Extra | What it does |
|---|---|---|---|
| `dryrun_keyless.json` | No | — | Sun + weather + prompt (API-format). |
| `step2_full_nanobanana.json` | Yes | Gemini image node | Recce + dress the Street View plate. |
| `step2_full_nanobanana_UI.json` | Yes | Gemini image node | Same graph in UI format. |
| `step2_v2_globe_setcast.json` | Yes | Gemini image node | Globe picker + Set & Cast. |
| `step2_v3_story.json` | Yes | Gemini text + image | Shoot Time + story brief + dress. |
| `gen_references.json` | No | Gemini image node | Batch the example reference stills. |

The Gemini nodes are **not** this pack. Install your usual ComfyUI Gemini /
image-model custom nodes if you want those graphs to generate. Without them,
the Recce nodes still run and you can swap in any img2img subgraph.
