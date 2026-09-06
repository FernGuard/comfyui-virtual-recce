# Virtual Recce workflow guide

This document is the source of truth for the workflow shipped in this repository.

## Contents

1. [Current state](#1-current-state)
2. [What the workflow does](#2-what-the-workflow-does)
3. [What is included](#3-what-is-included)
4. [Requirements](#4-requirements)
5. [Installation](#5-installation)
6. [Credential setup](#6-credential-setup)
7. [Reference-image setup](#7-reference-image-setup)
8. [Open and run the workflow](#8-open-and-run-the-workflow)
9. [Node-by-node controls](#9-node-by-node-controls)
10. [Expected output](#10-expected-output)
11. [Node pack inventory](#11-node-pack-inventory)
12. [Security rules](#12-security-rules)
13. [Limitations](#13-limitations)
14. [Troubleshooting](#14-troubleshooting)
15. [Validation status](#15-validation-status)

## 1. Current state

| Area | State |
|---|---|
| Repository purpose | Installable ComfyUI custom-node pack plus one complete example workflow |
| Current ComfyUI workflow | `workflows/virtual_recce_story.json` |
| ComfyUI workflow count | 1 |
| Virtual Recce nodes | 9 registered nodes; workflow cleanup did not remove node functionality |
| Required reference files | 3 PNG files in `examples/` |
| Bundled credentials | None |
| Local model downloads | None required by the supplied workflow |
| Paid services | Google Maps Platform usage and ComfyUI Partner Node credits |
| Repository visibility during this cleanup | Private |
| End-to-end paid run | Not performed without user-supplied credentials and credits |

The repository is structurally ready to install and open. The workflow, node registrations, reference filenames, Python files, and frontend extension are checked without storing or using private credentials. A complete paid run still depends on the user's Maps key, ComfyUI login, available credits, internet access, and current provider availability.

## 2. What the workflow does

```text
Google Maps key
       |
       +-> Location Picker -> latitude / longitude / address
       |          |
       |          +-> Street View -> real location plate
       |          +-> Sun Position -> real light description
       |          +-> Weather -> forecast weather description
       |
Shoot Time -------+-> resolves and sends one explicit date/time pair to Sun and Weather

Street View plate + set image + actor images
       |
       +-> Set & Cast -> ordered reference batch and labels

Location + light + weather + reference labels
       |
       +-> Prompt Builder
       +-> Google Gemini text Partner Node writes one scene
       +-> Nano Banana Pro Partner Node creates the final image
       +-> Save Image
```

The supplied graph uses:

- a public landmark as the default location example;
- one synthetic science-fiction set reference;
- two synthetic character references;
- real Google Street View imagery for the chosen coordinates;
- calculated solar position for the selected local date and time;
- Open-Meteo forecast data for that date;
- ComfyUI's built-in Gemini Partner Nodes for text and image generation.

## 3. What is included

```text
comfyui-virtual-recce/
├── __init__.py
├── nodes.py
├── requirements.txt
├── README.md
├── WORKFLOW_GUIDE.md
├── SECURITY.md
├── THIRD_PARTY_NOTICES.md
├── LICENSE
├── examples/
│   ├── ref_env_scifi_lab.png
│   ├── ref_char_hero.png
│   └── ref_char_woman.png
├── tests/
│   └── test_repository.py
├── web/
│   ├── vr_location_globe.js
│   └── vendor/
│       ├── globe.gl-2.46.2.bundle.mjs
│       ├── earth-blue-marble.jpg
│       └── earth-topology.png
└── workflows/
    └── virtual_recce_story.json
```

Historical drafts, API-format dry runs, reference-generation graphs, and intermediate versions are intentionally excluded.

## 4. Requirements

### 4.1 ComfyUI

Use a current ComfyUI version. The workflow requires these built-in node IDs:

- `LoadImage`
- `SaveImage`
- `GeminiNodeV2`
- `GeminiImage2Node`

The last two are built-in ComfyUI Partner Nodes, not nodes supplied by this repository and not a separate custom-node package.

The verified local baseline for this cleanup was:

- ComfyUI `0.34.2`
- ComfyUI frontend `1.49.6`

This is a verified baseline, not a promise that every older release works. ComfyUI's official Partner Node documentation recommends keeping ComfyUI current. If either Gemini node is missing, update ComfyUI before troubleshooting this pack.

Official references:

- [ComfyUI Partner Nodes overview](https://docs.comfy.org/tutorials/partner-nodes/overview)
- [Google Gemini Partner Nodes](https://docs.comfy.org/tutorials/partner-nodes/google/gemini)
- [ComfyUI credits](https://docs.comfy.org/interface/credits)

### 4.2 Python packages

The pack installs these dependencies from `requirements.txt`:

- `requests`
- `astral>=3.2`
- `timezonefinder>=6.0`

ComfyUI already provides Python, PyTorch, NumPy, and Pillow.

### 4.3 Accounts and paid access

You need two separate forms of access:

| Service | What you need | Used by |
|---|---|---|
| Google Maps Platform | A user-supplied API key with billing configured and two APIs enabled | Location Picker and Street View Reference |
| ComfyUI Partner Nodes | A logged-in ComfyUI account with a positive credit balance | Google Gemini text and Nano Banana Pro image nodes |
| Open-Meteo | Nothing | Weather node |

The workflow does **not** ask for a Google Gemini or Google AI Studio key. Gemini authentication is handled by ComfyUI's Partner Node account system.

### 4.4 Network access

Internet access is required for:

- Google Geocoding API;
- Google Street View Static API;
- Open-Meteo;
- ComfyUI Partner Nodes.

The globe module and earth textures are bundled in `web/vendor/` and do not require a CDN.

Manual latitude and longitude controls continue to work if the globe visual cannot load, but the remote data and generation calls still require internet access.

### 4.5 Hardware

The supplied generation nodes run through ComfyUI Partner APIs. No local checkpoint is required. The Virtual Recce data nodes do not require a GPU.

## 5. Installation

### 5.1 Install with ComfyUI Manager

1. Open ComfyUI.
2. Open **Manager**.
3. Open **Custom Nodes Manager**.
4. Choose **Install via Git URL**.
5. Paste:

   ```text
   https://github.com/FernGuard/comfyui-virtual-recce
   ```

6. Complete the installation.
7. Restart ComfyUI.
8. Right-click the canvas and search for `Recce`.

If this GitHub repository is private, the installation environment must have authenticated access. A user without repository access cannot clone a private repository.

### 5.2 Install manually on macOS or Linux

```sh
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/FernGuard/comfyui-virtual-recce.git
/path/to/ComfyUI/python -m pip install -r comfyui-virtual-recce/requirements.txt
```

Replace `/path/to/ComfyUI/python` with the interpreter used by that ComfyUI installation. Common installations use a `.venv/bin/python` interpreter.

### 5.3 Install manually on Windows

From PowerShell:

```powershell
cd C:\path\to\ComfyUI\custom_nodes
git clone https://github.com/FernGuard/comfyui-virtual-recce.git
C:\path\to\ComfyUI\python.exe -m pip install -r .\comfyui-virtual-recce\requirements.txt
```

Portable installations often include an embedded Python interpreter. Use the interpreter that launches ComfyUI, not an unrelated system Python.

### 5.4 Confirm the installation

After restarting ComfyUI, right-click the canvas and search for:

```text
Recce · Location Picker (Globe)
```

If that node appears, the Python pack and frontend registration loaded. If no `Recce` nodes appear, inspect the ComfyUI startup console for an import error and reinstall the packages from `requirements.txt` into ComfyUI's own Python environment.

## 6. Credential setup

### 6.1 Create the Google Maps key

1. Open [Google Cloud credentials](https://console.cloud.google.com/apis/credentials).
2. Select or create a Google Cloud project.
3. Configure billing for Google Maps Platform.
4. Enable **Geocoding API**.
5. Enable **Street View Static API**.
6. Create an API key.
7. Restrict the key to those two APIs. Add application restrictions appropriate for your environment if they do not block local server-side requests.

Paste the key only into the workflow's **Recce · Google Maps Key** node.

The repository does not load `.env` files. Exporting a variable or creating a `.env` file will not populate the widget.

### 6.2 Enable ComfyUI Partner Nodes

1. Open ComfyUI settings.
2. Go to **User** and sign in to your ComfyUI account.
3. Go to **Credits**.
4. Confirm that the balance is greater than zero.

ComfyUI uses prepaid credits for the `GeminiNodeV2` and `GeminiImage2Node` calls. Current prices and model availability are controlled by ComfyUI and the provider, not by this repository.

A typical address-mode run can make these remote calls:

1. one Google Geocoding request;
2. one free Street View metadata request;
3. one billed Street View image request when imagery exists;
4. one Open-Meteo forecast request;
5. one paid Gemini text Partner Node call;
6. one paid Gemini image Partner Node call.

ComfyUI uploads the Street View plate, set reference, actor references, and generated prompts to hosted Partner Node services for the two Gemini calls. Their moderation, privacy, and retention terms apply. Do not use private or uncleared references without reviewing those terms.

## 7. Reference-image setup

The workflow expects these exact filenames:

```text
ref_env_scifi_lab.png
ref_char_hero.png
ref_char_woman.png
```

Copy all three files from this repository's `examples/` directory into the input directory used by your ComfyUI installation.

Typical target:

```text
/path/to/ComfyUI/input/
```

Some ComfyUI Desktop setups use a shared input folder. If the workflow reports a missing image, use each `Load Image` node's selector and choose the matching copied file manually.

These are synthetic test references created for this repository and provided under its MIT license. They contain no embedded ComfyUI workflow or prompt metadata. Replace them with your own cleared set and cast references for production use, then update the corresponding `Load Image` nodes.

## 8. Open and run the workflow

### 8.1 Open

Use either method:

- In ComfyUI, choose **Workflow -> Open** and select `workflows/virtual_recce_story.json`.
- Drag `workflows/virtual_recce_story.json` onto the ComfyUI canvas.

### 8.2 Confirm there are no missing nodes

The graph should open without red or missing-node placeholders. If `GeminiNodeV2` or `GeminiImage2Node` is missing, update ComfyUI. Do not search for an unrelated Gemini custom-node pack.

### 8.3 Configure the graph

1. In **Recce · Google Maps Key**, paste your Maps key.
2. In **Recce · Location Picker (Globe)**, enter an address or click the globe.
3. In **Recce · Shoot Time**, set a local shoot date and 24-hour time.
4. Check the three `Load Image` nodes and replace the test references if desired.
5. In **Recce · Set & Cast**, name actor 1 and actor 2 so the prompt labels match the images.
6. Optionally add direction or genre and adjust the camera/style text in **Recce · Prompt Builder**.
7. Review the selected Gemini text and image models.
8. Queue the workflow with **Run**, or press `Ctrl/Cmd + Enter`.

### 8.4 Recommended first run

For the first run:

- keep the default public landmark;
- leave the date blank so it resolves to today;
- keep the time at `17:30`;
- keep `timezone` set to `auto`;
- use the three bundled test references;
- use the saved fixed seeds.

This isolates installation and account problems before you customize the creative inputs.

## 9. Node-by-node controls

### 9.1 Recce · Google Maps Key

Purpose: holds one Maps key and sends it to every Recce node that needs it.

- Paste the key into `google_api_key`.
- Never commit or share the workflow while the key is still present.

### 9.2 Recce · Location Picker (Globe)

Purpose: resolves an address or coordinates and sends one location to the rest of the graph.

| Control | Meaning |
|---|---|
| `address` | Address or place name for Google Geocoding |
| `latitude`, `longitude` | Manual coordinate fallback or globe result |
| `input_mode: auto` | Uses a non-empty address; otherwise uses coordinates |
| `input_mode: address` | Always geocodes the address |
| `input_mode: coordinates` | Uses coordinates and attempts reverse geocoding |

Clicking the globe updates latitude and longitude and changes the mode to `coordinates`. Typing an address changes the mode back to `address`.

### 9.3 Recce · Shoot Time

Purpose: guarantees that Sun Position and Weather use the same date and time.

- Date format: `YYYY-MM-DD`
- Time format: `HH:MM` in 24-hour time
- Blank date: the current calendar date on the machine running ComfyUI
- Blank time: the current local clock time on the machine running ComfyUI

The node resolves blank values once, then sends the same explicit strings to both Sun Position and Weather. Weather still has a noon fallback if it is used without Shoot Time and its own time widget is blank. The supplied workflow always routes through Shoot Time, so that fallback does not apply here.

For a remote location in another timezone, enter the destination's date and local shoot time explicitly.

### 9.4 Recce · Street View Reference

Purpose: retrieves the real location plate.

| Control | Meaning |
|---|---|
| `heading` | Camera direction from 0 to 360 degrees |
| `pitch` | Camera tilt from -90 to 90 degrees |
| `fov` | Horizontal field of view from 10 to 120 degrees |
| `width`, `height` | Output dimensions, up to 640 by 640 in this node |

The node first requests Street View metadata. If no imagery exists, it returns a blank plate and a status message rather than billing for an unusable image request.

### 9.5 Recce · Sun Position (real light)

Purpose: calculates real solar azimuth and elevation for the location and time.

Keep `timezone` set to `auto` unless you need to supply an explicit IANA timezone such as `America/Los_Angeles`.

The output describes the sun direction, elevation, lighting phase, and shadow character for the prompt.

### 9.6 Recce · Location Weather

Purpose: requests hourly cloud cover and weather conditions from Open-Meteo.

No key is required. Dates outside the forecast window return `weather unavailable for this date (outside forecast range)`.

### 9.7 Load Image nodes

Purpose: load one set reference and two actor references.

The saved graph expects:

1. `ref_env_scifi_lab.png` as the set reference;
2. `ref_char_hero.png` as actor 1;
3. `ref_char_woman.png` as actor 2.

### 9.8 Recce · Set & Cast

Purpose: resizes and batches the real plate, set reference, and two actor references, then creates text labels that identify the order of those images.

- `resolution` controls the square size used for the reference batch.
- `actor_1_name` and `actor_2_name` should match the people depicted.
- At least one image must be connected.

### 9.9 Recce · Prompt Builder

Purpose: builds a labeled brief from the grounded location, lighting, weather, and reference information.

Optional fields:

- `set_description`
- `character_description`
- `direction`
- `camera_and_style`

The latest workflow already receives its set and cast labels from **Set & Cast**. Use `direction` for genre, tone, or a specific dramatic beat. Use `camera_and_style` for photographic treatment.

### 9.10 Google Gemini

Node ID: `GeminiNodeV2`

Purpose: turns the labeled factual brief into one concise cinematic scene while preserving the real light and weather.

The saved graph selects `Gemini 3.1 Pro`, high thinking, and a `32768` maximum-output-token cap. The model stops when the short scene is complete; the higher cap prevents internal thinking from consuming all available output space. Provider models can change. If that model becomes unavailable, choose a current Gemini text model without changing the graph wiring.

### 9.11 Nano Banana Pro (Google Gemini Image)

Node ID: `GeminiImage2Node`

Purpose: creates the final 16:9 image from the story prompt and the ordered reference batch.

Saved settings:

- model: `gemini-3-pro-image-preview`
- aspect ratio: `16:9`
- resolution: `2K`
- response: `IMAGE`
- seed: fixed at `42`

A fixed seed is a best-effort consistency control. Remote model output is not guaranteed to be identical across runs.

### 9.12 Save Image

Purpose: writes the generated image to the active ComfyUI output directory.

Filename prefix:

```text
VirtualRecce_story
```

## 10. Expected output

A successful run is intended to produce one cinematic image that:

- uses the selected Street View location as the spatial base;
- follows the selected date, local time, calculated sun direction, and weather;
- applies the set-dressing reference;
- places the two reference characters into the scene;
- uses the generated short scene as the image prompt.

The final image is written to the ComfyUI output directory with the `VirtualRecce_story` prefix and ComfyUI's normal numeric suffix.

Intermediate outputs include:

- formatted address;
- Street View status;
- sun azimuth, elevation, phase, and light description;
- weather description and cloud-cover percentage;
- ordered reference notes;
- final labeled prompt;
- Gemini's scene text.

## 11. Node pack inventory

All nine nodes remain available even though the supplied workflow does not need every utility node.

| Node ID | Display name | Used in supplied workflow |
|---|---|---:|
| `VRGoogleMapsKey` | Recce · Google Maps Key | Yes |
| `VRShootTime` | Recce · Shoot Time | Yes |
| `VRLocationPicker` | Recce · Location Picker (Globe) | Yes |
| `VRSetAndCast` | Recce · Set & Cast | Yes |
| `VRGeocodeAddress` | Recce · Geocode Address | No; standalone utility retained |
| `VRStreetViewReference` | Recce · Street View Reference | Yes |
| `VRSunPosition` | Recce · Sun Position (real light) | Yes |
| `VRLocationWeather` | Recce · Location Weather | Yes |
| `VRReccePromptBuilder` | Recce · Prompt Builder | Yes |

`VRGeocodeAddress` remains because it is useful when building a smaller address-only graph. The latest workflow uses the combined `VRLocationPicker` instead.

## 12. Security rules

1. Never commit a real API key.
2. Never upload a workflow containing a filled key to an issue, pull request, chat, or public repository.
3. Clear the key widget before saving a workflow intended for sharing.
4. Restrict the Maps key to the required APIs.
5. Monitor Google Cloud usage and quotas.
6. Use the ComfyUI account login for Partner Nodes. Do not paste account tokens into this workflow.
7. If a key is ever committed, remove it from history and rotate it immediately.

ComfyUI workflow JSON can serialize widget values. A key pasted into a widget may be written into the JSON when the workflow is saved.

## 13. Limitations

- Google Maps Platform calls may incur charges and require billing.
- Street View is limited to locations where Google has imagery.
- Street View Static output in this node is capped at 640 by 640 pixels.
- Street View imagery date may not match the selected shoot date. The chosen date controls sun and forecast weather, not the date when Google captured the plate.
- Weather uses Open-Meteo's forecast endpoint. Historical weather and dates outside the forecast window are not supported by this node.
- The globe frontend uses bundled `globe.gl 2.46.2` code and `three-globe 2.45.2` textures. It makes no runtime CDN request. Manual coordinates remain available if WebGL is unavailable.
- Gemini text and image generation consume ComfyUI credits and depend on provider availability.
- Remote generative results are not fully deterministic, even with a fixed seed.
- The workflow is a visual-planning tool, not a substitute for permits, access checks, releases, safety planning, or an on-site scout.
- Users are responsible for Google Maps terms, ComfyUI Partner Node terms, location rights, and rights to their own reference images and outputs.

## 14. Troubleshooting

### No Recce nodes appear

Cause: the pack failed to import or its dependencies were installed into the wrong Python environment.

Fix:

1. Inspect the ComfyUI startup console.
2. Confirm that this repository is inside `ComfyUI/custom_nodes/`.
3. Install `requirements.txt` with the Python interpreter used by ComfyUI.
4. Restart ComfyUI.

### Gemini nodes are missing or red

Cause: ComfyUI is outdated or its built-in API nodes failed to import.

Fix:

1. Update ComfyUI.
2. Restart it.
3. Search the canvas for `Google Gemini` and `Nano Banana Pro`.
4. Do not install an unrelated Gemini custom-node pack for these node IDs.

### Partner Node asks for login or reports insufficient credits

1. Open **Settings -> User** and sign in.
2. Open **Settings -> Credits**.
3. Add or confirm a positive prepaid balance.
4. Queue again.

### Location Picker or Street View reports a missing key

Paste the key into **Recce · Google Maps Key** and confirm that its output remains connected to both downstream key inputs.

### Google returns `REQUEST_DENIED`

Check:

- billing is enabled;
- Geocoding API is enabled;
- Street View Static API is enabled;
- API restrictions include both services;
- application restrictions allow requests from the machine running ComfyUI;
- the project quota has not been exhausted.

### Street View returns a blank image

The selected point may not have Street View coverage. Try a nearby road or a different location. Check the node's status output.

### Weather says unavailable

Use today or a date within approximately 16 days. This node does not use the historical archive API.

### Load Image reports a missing file

Copy the three files from `examples/` into the active ComfyUI input directory. If your installation uses a shared input directory, select each image manually from its `Load Image` node.

### Globe visual does not load

Confirm that the vendored files under `web/vendor/` are present and that WebGL is available. You can still enter latitude and longitude directly and set `input_mode` to `coordinates`. The rest of the workflow does not depend on the globe visual.

### Output ignores a reference or changes a face

Remote image models may not preserve identity perfectly. Improve the reference images, use clear actor names, tighten the story prompt, or replace the final generation section with a model designed for stronger identity control.

## 15. Validation status

The checks can be run locally from the repository root:

```sh
python -m unittest discover -s tests -v
python -m py_compile nodes.py __init__.py tests/test_repository.py
node --check web/vr_location_globe.js
node --check web/vendor/globe.gl-2.46.2.bundle.mjs
```

The cleaned repository is checked for:

- repository unit tests covering structure, workflow integrity, privacy, and request-error wrapping;
- Python compilation of `nodes.py`, `__init__.py`, and `tests/test_repository.py`;
- JavaScript syntax for the globe extension and vendored module;
- exactly one workflow file;
- all Virtual Recce workflow node IDs registered by this pack;
- required built-in ComfyUI node IDs documented for the supplied graph;
- valid workflow links and referenced node IDs;
- exactly three required example images with matching workflow filenames;
- stripped PNG metadata;
- empty Google Maps widget values;
- no bundled credentials;
- no personal absolute paths or private operational notes;
- no removed-provider names, code, node mappings, documentation, workflow content, or reachable Git blobs;
- vendored globe code, textures, and license notice with no runtime CDN import;
- repository secret scanning.

A live ComfyUI import and prompt-validator smoke was run locally during this cleanup against ComfyUI `0.34.2`. That smoke is not part of the committed unit tests. The validation does not make paid external calls. A true end-to-end image run requires the user's Maps key, ComfyUI account, positive credits, network access, and provider availability.
