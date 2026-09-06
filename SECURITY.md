# Security

## API keys and account access

This repository ships no API keys, tokens, passwords, or account credentials.

The current workflow needs:

- a Google Maps Platform key entered into the `Recce · Google Maps Key` widget;
- a ComfyUI account login and prepaid credits handled by ComfyUI for its built-in Gemini Partner Nodes.

This pack does not load `.env` files and does not read a Maps key from the shell environment. Paste the Maps key into the widget only when you are ready to run.

ComfyUI can serialize widget values into workflow JSON. Before saving, exporting, committing, uploading, or sharing a workflow:

1. clear the Maps key widget;
2. save the sanitized workflow;
3. inspect the JSON if it will be published.

Restrict the Maps key to **Geocoding API** and **Street View Static API**. Monitor its usage and quotas. If a credential is ever committed, rotate it immediately and remove it from reachable Git history.

The nodes do not print credential values.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a public issue containing a suspected key, token, private path, or exploit detail.
