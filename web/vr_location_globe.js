// Virtual Recce - interactive 3D globe widget for the Location Picker node.
// Two-way sync: edit the address and the globe + lat/long geocode to match; move
// the globe (or edit lat/long) and the address reverse-geocodes to match. Whichever
// you touch, the other updates immediately. Geocoding uses the wired Google Maps key.
import { app } from "../../scripts/app.js";

const VENDOR_BASE = new URL("./vendor/", import.meta.url);
const GLOBE_ESM = new URL("globe.gl-2.46.2.bundle.mjs", VENDOR_BASE).href;
const EARTH_TEX = new URL("earth-blue-marble.jpg", VENDOR_BASE).href;
const BUMP_TEX = new URL("earth-topology.png", VENDOR_BASE).href;

let globePromise = null;
function loadGlobe() {
  if (!globePromise) {
    globePromise = import(GLOBE_ESM)
      .then((m) => m.default || m.Globe || m)
      .catch((err) => {
        console.error("[VirtualRecce] globe.gl failed to load", err);
        globePromise = null;
        throw err;
      });
  }
  return globePromise;
}

const widgetByName = (node, name) => (node.widgets || []).find((w) => w.name === name);

// Resolve the Google Maps key: this node's own widget, else trace the
// google_api_key input link back to the source node's widget (the Maps Key node).
function resolveApiKey(node) {
  const own = widgetByName(node, "google_api_key");
  if (own && String(own.value || "").trim()) return String(own.value).trim();
  const inp = (node.inputs || []).find((i) => i.name === "google_api_key");
  const links = app.graph && app.graph.links;
  if (inp && inp.link != null && links) {
    const lk = links[inp.link];
    const originId = Array.isArray(lk) ? lk[1] : lk && lk.origin_id;
    const src = originId != null && app.graph.getNodeById ? app.graph.getNodeById(originId) : null;
    if (src) {
      const sw = (src.widgets || []).find((x) => x.name === "google_api_key");
      if (sw && String(sw.value || "").trim()) return String(sw.value).trim();
    }
  }
  return "";
}

async function geocode(params, key) {
  const url =
    "https://maps.googleapis.com/maps/api/geocode/json?" +
    new URLSearchParams({ ...params, key }).toString();
  const r = await fetch(url);
  const d = await r.json();
  if (d.status !== "OK" || !d.results || !d.results.length) {
    throw new Error(d.status || "geocode_failed");
  }
  return d.results[0];
}

app.registerExtension({
  name: "VirtualRecce.LocationGlobe",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "VRLocationPicker") return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const created = onCreated ? onCreated.apply(this, arguments) : undefined;
      const node = this;

      const container = document.createElement("div");
      container.style.cssText =
        "width:100%;height:300px;position:relative;border-radius:8px;overflow:hidden;" +
        "background:#05070d;border:1px solid #1c2333;";

      const hint = document.createElement("div");
      hint.textContent = "Loading globe…";
      hint.style.cssText =
        "position:absolute;left:8px;bottom:6px;z-index:2;pointer-events:none;" +
        "font:11px/1.3 ui-monospace,monospace;color:#7fd1ff;" +
        "background:rgba(0,0,0,.45);padding:2px 6px;border-radius:4px;max-width:92%;";
      container.appendChild(hint);

      const widget = node.addDOMWidget("vr_globe", "div", container, { serialize: false });
      widget.computeSize = (w) => [w, 300];
      node.size = [Math.max(node.size?.[0] || 0, 360), Math.max(node.size?.[1] || 0, 560)];

      const latW = () => widgetByName(node, "latitude");
      const lngW = () => widgetByName(node, "longitude");
      const addrW = () => widgetByName(node, "address");
      const modeW = () => widgetByName(node, "input_mode");
      const setMode = (m) => { const w = modeW(); if (w && w.value !== m) w.value = m; };

      let globe = null;
      let ready = false;
      let busy = false;          // guard against sync feedback loops
      let addrTimer = null;

      const coords = () => ({
        lat: Number(latW()?.value ?? 34.1184),
        lng: Number(lngW()?.value ?? -118.3004),
      });

      const setMarker = (lat, lng, fly) => {
        if (!globe) return;
        globe.pointsData([{ lat, lng }]);
        if (fly) globe.pointOfView({ lat, lng, altitude: 1.6 }, 800);
      };

      const say = (msg) => { hint.textContent = msg; };
      const showCoords = (extra) => {
        const { lat, lng } = coords();
        say(`${lat.toFixed(5)}, ${lng.toFixed(5)}${extra ? "  ·  " + extra : "  ·  drag to spin, click to place"}`);
      };

      // ADDRESS -> coordinates (forward geocode)
      const fromAddress = async () => {
        if (busy) return;
        const address = String(addrW()?.value || "").trim();
        if (!address) return;
        const key = resolveApiKey(node);
        if (!key) { setMode("address"); say("no Maps key wired — address will resolve at run time"); return; }
        busy = true;
        try {
          say("geocoding address…");
          const res = await geocode({ address }, key);
          const loc = res.geometry.location;
          if (latW()) latW().value = Number(loc.lat.toFixed(6));
          if (lngW()) lngW().value = Number(loc.lng.toFixed(6));
          if (addrW()) addrW().value = res.formatted_address || address;
          setMode("coordinates");          // coords are now exact — let them drive
          setMarker(loc.lat, loc.lng, true);
          showCoords(res.formatted_address || "");
          node.setDirtyCanvas(true, true);
        } catch (e) {
          setMode("address");              // fall back to run-time geocode
          say(`could not geocode ("${e.message}") — will resolve at run time`);
        } finally { busy = false; }
      };

      // coordinates -> ADDRESS (reverse geocode)
      const fromCoords = async (fly) => {
        const { lat, lng } = coords();
        setMode("coordinates");
        setMarker(lat, lng, fly);
        showCoords("resolving…");
        if (busy) return;
        const key = resolveApiKey(node);
        if (!key) { showCoords("no Maps key wired"); return; }
        busy = true;
        try {
          const res = await geocode({ latlng: `${lat},${lng}` }, key);
          if (addrW()) addrW().value = res.formatted_address || "";
          showCoords(res.formatted_address || "");
          node.setDirtyCanvas(true, true);
        } catch (e) {
          showCoords(`${lat.toFixed(3)}, ${lng.toFixed(3)}`);
        } finally { busy = false; }
      };

      loadGlobe()
        .then((Globe) => {
          globe = Globe()(container)
            .globeImageUrl(EARTH_TEX)
            .bumpImageUrl(BUMP_TEX)
            .backgroundColor("rgba(0,0,0,0)")
            .pointColor(() => "#ff4d4d")
            .pointAltitude(0.02)
            .pointRadius(0.6)
            .atmosphereColor("#3a86ff")
            .atmosphereAltitude(0.18);

          const fit = () => {
            globe.width(container.clientWidth || 340);
            globe.height(container.clientHeight || 300);
          };
          fit();
          new ResizeObserver(fit).observe(container);

          if (globe.controls) {
            globe.controls().autoRotate = true;
            globe.controls().autoRotateSpeed = 0.6;
            container.addEventListener(
              "pointerdown",
              () => { if (globe.controls) globe.controls().autoRotate = false; },
              { once: true }
            );
          }

          const { lat, lng } = coords();
          setMarker(lat, lng, true);
          showCoords();
          ready = true;

          // Globe click -> set coords + reverse-geocode the address
          globe.onGlobeClick(({ lat, lng }) => {
            if (latW()) latW().value = Number(lat.toFixed(6));
            if (lngW()) lngW().value = Number(lng.toFixed(6));
            fromCoords(false);
          });
        })
        .catch(() => { say("Globe failed to load. Address + lat/long still work."); });

      // Hand-edits to latitude/longitude -> reverse-geocode the address
      for (const name of ["latitude", "longitude"]) {
        const w = widgetByName(node, name);
        if (!w) continue;
        const prev = w.callback;
        w.callback = function () {
          const rv = prev ? prev.apply(this, arguments) : undefined;
          if (ready && !busy) fromCoords(true);
          return rv;
        };
      }

      // Editing the address -> forward-geocode (debounced)
      const aw = widgetByName(node, "address");
      if (aw) {
        const prevA = aw.callback;
        aw.callback = function () {
          const rv = prevA ? prevA.apply(this, arguments) : undefined;
          if (ready && !busy) {
            clearTimeout(addrTimer);
            addrTimer = setTimeout(fromAddress, 250);
          }
          return rv;
        };
      }

      return created;
    };
  },
});
