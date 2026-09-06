// Virtual Recce — interactive 3D globe widget for the Location Picker node.
// Drag to spin the globe, click a spot to drop a coordinate. The marker and the
// latitude/longitude widgets stay in sync both ways; clicking clears `address`
// so the clicked point wins in 'auto' mode.
import { app } from "../../scripts/app.js";

const GLOBE_ESM = "https://esm.sh/globe.gl@2?bundle";
const EARTH_TEX = "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg";
const BUMP_TEX  = "https://unpkg.com/three-globe/example/img/earth-topology.png";

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
        "background:rgba(0,0,0,.45);padding:2px 6px;border-radius:4px;";
      container.appendChild(hint);

      const widget = node.addDOMWidget("vr_globe", "div", container, { serialize: false });
      widget.computeSize = (w) => [w, 300];
      node.size = [Math.max(node.size?.[0] || 0, 360), Math.max(node.size?.[1] || 0, 560)];

      const latW = () => widgetByName(node, "latitude");
      const lngW = () => widgetByName(node, "longitude");
      const addrW = () => widgetByName(node, "address");
      const modeW = () => widgetByName(node, "input_mode");
      const setMode = (m) => { const w = modeW(); if (w && w.value !== m) { w.value = m; } };

      let globe = null;
      let ready = false;

      const coords = () => ({
        lat: Number(latW()?.value ?? 34.1184),
        lng: Number(lngW()?.value ?? -118.3004),
      });

      const setMarker = (lat, lng, fly) => {
        if (!globe) return;
        globe.pointsData([{ lat, lng }]);
        if (fly) globe.pointOfView({ lat, lng, altitude: 1.6 }, 800);
      };

      const refreshHint = () => {
        const { lat, lng } = coords();
        hint.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}  ·  drag to spin, click to place`;
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
          refreshHint();
          ready = true;

          globe.onGlobeClick(({ lat, lng }) => {
            const la = Number(lat.toFixed(6));
            const lo = Number(lng.toFixed(6));
            if (latW()) latW().value = la;
            if (lngW()) lngW().value = lo;
            setMode("coordinates"); // the globe now explicitly drives location (beats the address)
            setMarker(la, lo, false);
            refreshHint();
            node.setDirtyCanvas(true, true);
          });
        })
        .catch(() => {
          hint.textContent = "Globe failed to load (offline?). Lat/long widgets still work.";
        });

      // Hand-edits to latitude/longitude fly the marker AND make coordinates drive.
      for (const name of ["latitude", "longitude"]) {
        const w = widgetByName(node, name);
        if (!w) continue;
        const prev = w.callback;
        w.callback = function () {
          const rv = prev ? prev.apply(this, arguments) : undefined;
          if (ready) {
            const { lat, lng } = coords();
            setMarker(lat, lng, true);
            refreshHint();
            setMode("coordinates");
          }
          return rv;
        };
      }

      // Typing an address makes the address drive again.
      const aw = widgetByName(node, "address");
      if (aw) {
        const prevA = aw.callback;
        aw.callback = function () {
          const rv = prevA ? prevA.apply(this, arguments) : undefined;
          if ((aw.value || "").trim()) setMode("address");
          return rv;
        };
      }

      return created;
    };
  },
});
