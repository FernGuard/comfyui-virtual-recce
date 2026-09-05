# Security

## API keys

This pack does not ship API keys. Never put keys, tokens, or credentials in
this repository, in issues, pull requests, or committed ComfyUI workflow JSON.

Paste keys into the Recce node widgets (or export them in your own shell).
The nodes fail if a required key is missing. They do not print key values.

Google Maps keys are billed to **your** accounts.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability). Do not open a public issue for a
suspected secret leak.

If you find a key in git history, report it privately and rotate the key
immediately.
