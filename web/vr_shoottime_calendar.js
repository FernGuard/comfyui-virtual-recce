// Virtual Recce - calendar date picker for the Shoot Time node's `date` field.
// Uses the browser-native date input: click to open the OS calendar (month/year
// navigation), or type YYYY-MM-DD. The native popup is rendered by the browser,
// so it can't be clipped or swallowed by the ComfyUI canvas. Blank = today.
import { app } from "../../scripts/app.js";

const widgetByName = (node, name) => (node.widgets || []).find((w) => w.name === name);

app.registerExtension({
  name: "VirtualRecce.ShootTimeCalendar",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "VRShootTime") return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const created = onCreated ? onCreated.apply(this, arguments) : undefined;
      const node = this;

      const dateW = widgetByName(node, "date");
      if (dateW) {                       // hide the plain text `date` widget
        dateW.hidden = true;
        dateW.computeSize = () => [0, -4];
      }

      const wrap = document.createElement("div");
      wrap.style.cssText = "width:100%;box-sizing:border-box;";

      const input = document.createElement("input");
      input.type = "date";
      input.value = (dateW && dateW.value) || "";      // YYYY-MM-DD or blank
      input.style.cssText =
        "width:100%;box-sizing:border-box;padding:5px 8px;border-radius:6px;" +
        "border:1px solid #2a3550;background:#0f1420;color:#cfe3ff;color-scheme:dark;" +
        "font:12px ui-monospace,monospace;outline:none;cursor:pointer;";
      wrap.appendChild(input);

      const widget = node.addDOMWidget("vr_date", "div", wrap, { serialize: false });
      widget.computeSize = (w) => [w, 34];

      const commit = () => {
        if (dateW) dateW.value = input.value || "";     // blank -> today (handled server-side)
        node.setDirtyCanvas(true, true);
      };
      input.addEventListener("change", commit);
      input.addEventListener("input", commit);
      // clicking anywhere on the field opens the native picker where supported
      input.addEventListener("click", () => { if (input.showPicker) { try { input.showPicker(); } catch (e) {} } });

      return created;
    };
  },
});
