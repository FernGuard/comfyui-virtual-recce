# Virtual Recce

Virtual Recce is a ComfyUI custom-node pack for data-grounded location scouting. It combines a real location, a real Street View plate, calculated sunlight, forecast weather, set references, and cast references into one cinematic image workflow.

## Start here

Read **[WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)** before opening the workflow. It is the single source of truth for requirements, installation, credentials, operation, limitations, troubleshooting, and validation status.

## What is included

| Item | Included |
|---|---:|
| Installable Virtual Recce node pack | Yes |
| Interactive location globe extension | Yes |
| Current ComfyUI workflow | `workflows/virtual_recce_story.json` |
| ComfyUI workflow count | 1 |
| Required test/reference images | 3 files in `examples/` |
| API keys or credentials | No |
| Historical or intermediate workflows | No |

All nine Virtual Recce nodes remain in the pack. The cleanup removed obsolete workflow files, not node functionality.

## Minimum requirements

- A current ComfyUI installation that includes the built-in `GeminiNodeV2` and `GeminiImage2Node` Partner Nodes
- A ComfyUI account with a positive credit balance for those Gemini Partner Nodes
- A Google Maps Platform key with **Geocoding API** and **Street View Static API** enabled
- Internet access

No local checkpoint download is required by the supplied workflow.

## Install

### ComfyUI Manager

Use **Custom Nodes Manager -> Install via Git URL** and enter:

```text
https://github.com/FernGuard/comfyui-virtual-recce
```

Restart ComfyUI after installation. If the repository is private, the installer must have authenticated GitHub access.

### Manual

```sh
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/FernGuard/comfyui-virtual-recce.git
/path/to/ComfyUI/python -m pip install -r comfyui-virtual-recce/requirements.txt
```

Use the Python interpreter that launches your ComfyUI installation. Restart ComfyUI after installing the dependencies.

## Run the supplied workflow

1. Follow the exact setup in [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md).
2. Copy the three files from `examples/` into your ComfyUI input directory.
3. Open `workflows/virtual_recce_story.json` in ComfyUI.
4. Paste your Google Maps key into **Recce · Google Maps Key**.
5. Confirm that you are logged into ComfyUI and have Partner Node credits.
6. Select a location and shoot time, then queue the workflow.

Generated files are saved with the prefix `VirtualRecce_story` in the active ComfyUI output directory.

## Security

The repository contains no credentials. Do not commit a workflow after pasting a key into a widget because ComfyUI can serialize widget values into workflow JSON. See [SECURITY.md](SECURITY.md).

## License

Code, documentation, and the synthetic test images are provided under the [MIT License](LICENSE). Vendored frontend notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
