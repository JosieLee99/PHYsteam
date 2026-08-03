const manifest = {"name":"PHYsteam","author":"you","flags":["debug"],"api_version":1};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

var DefaultContext = {
  color: undefined,
  size: undefined,
  className: undefined,
  style: undefined,
  attr: undefined
};
var IconContext = SP_REACT.createContext && SP_REACT.createContext(DefaultContext);

var __assign = window && window.__assign || function () {
  __assign = Object.assign || function (t) {
    for (var s, i = 1, n = arguments.length; i < n; i++) {
      s = arguments[i];
      for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p)) t[p] = s[p];
    }
    return t;
  };
  return __assign.apply(this, arguments);
};
var __rest = window && window.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function Tree2Element(tree) {
  return tree && tree.map(function (node, i) {
    return SP_REACT.createElement(node.tag, __assign({
      key: i
    }, node.attr), Tree2Element(node.child));
  });
}
function GenIcon(data) {
  // eslint-disable-next-line react/display-name
  return function (props) {
    return SP_REACT.createElement(IconBase, __assign({
      attr: __assign({}, data.attr)
    }, props), Tree2Element(data.child));
  };
}
function IconBase(props) {
  var elem = function (conf) {
    var attr = props.attr,
      size = props.size,
      title = props.title,
      svgProps = __rest(props, ["attr", "size", "title"]);
    var computedSize = size || conf.size || "1em";
    var className;
    if (conf.className) className = conf.className;
    if (props.className) className = (className ? className + " " : "") + props.className;
    return SP_REACT.createElement("svg", __assign({
      stroke: "currentColor",
      fill: "currentColor",
      strokeWidth: "0"
    }, conf.attr, attr, svgProps, {
      className: className,
      style: __assign(__assign({
        color: props.color || conf.color
      }, conf.style), props.style),
      height: computedSize,
      width: computedSize,
      xmlns: "http://www.w3.org/2000/svg"
    }), title && SP_REACT.createElement("title", null, title), props.children);
  };
  return IconContext !== undefined ? SP_REACT.createElement(IconContext.Consumer, null, function (conf) {
    return elem(conf);
  }) : elem(DefaultContext);
}

// THIS FILE IS AUTO GENERATED
function FaCompactDisc (props) {
  return GenIcon({"tag":"svg","attr":{"viewBox":"0 0 496 512"},"child":[{"tag":"path","attr":{"d":"M248 8C111 8 0 119 0 256s111 248 248 248 248-111 248-248S385 8 248 8zM88 256H56c0-105.9 86.1-192 192-192v32c-88.2 0-160 71.8-160 160zm160 96c-53 0-96-43-96-96s43-96 96-96 96 43 96 96-43 96-96 96zm0-128c-17.7 0-32 14.3-32 32s14.3 32 32 32 32-14.3 32-32-14.3-32-32-32z"}}]})(props);
}

const getConfig = callable("get_config");
const saveConfig = callable("save_config");
const listDrives = callable("list_removable_drives");
const clearKnownGames = callable("clear_known_games");
const debugListDrives = callable("debug_list_drives");
function Content() {
    var _a;
    const [config, setConfig] = SP_REACT.useState(null);
    const [drives, setDrives] = SP_REACT.useState([]);
    const [saving, setSaving] = SP_REACT.useState(false);
    const [diagnostics, setDiagnostics] = SP_REACT.useState(null);
    const refreshDrives = () => {
        listDrives().then(setDrives).catch(() => setDrives([]));
    };
    SP_REACT.useEffect(() => {
        getConfig().then(setConfig);
        refreshDrives();
        const interval = setInterval(refreshDrives, 3000);
        return () => clearInterval(interval);
    }, []);
    if (!config) {
        return (window.SP_REACT.createElement(DFL.PanelSection, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null, "Loading PHYsteam config\u2026")));
    }
    const update = async (patch) => {
        const next = { ...config, ...patch };
        setConfig(next);
        setSaving(true);
        try {
            await saveConfig(next);
        }
        finally {
            setSaving(false);
        }
    };
    const driveOptions = [
        { data: "__auto__", label: "Auto-detect last removable drive" },
        ...drives.map((d) => ({ data: d, label: d })),
    ];
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: "PHYsteam" },
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { label: "Mode", description: "Auto-detect watches every removable drive. Fixed watches one specific drive." },
                window.SP_REACT.createElement(DFL.Dropdown, { rgOptions: [
                        { data: "auto", label: "Auto-detect" },
                        { data: "fixed", label: "Fixed drive" },
                    ], selectedOption: config.mode, onChange: (o) => update({ mode: o.data }) }))),
        config.mode === "fixed" && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { label: "Drive" },
                window.SP_REACT.createElement(DFL.Dropdown, { rgOptions: driveOptions, selectedOption: (_a = config.drive) !== null && _a !== void 0 ? _a : "__auto__", onChange: (o) => update({ drive: o.data === "__auto__" ? null : o.data }) })))),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ToggleField, { label: "Require cartridge", description: "Force-close a tracked game if its drive is removed or missing at launch.", checked: config.require_card, onChange: (checked) => update({ require_card: checked }) })),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ToggleField, { label: "Dry run (log only, don't launch)", description: "Detects cartridges and logs what it would do, but never actually launches a game. Use this to test insert/remove detection safely.", checked: config.dry_run, onChange: (checked) => update({ dry_run: checked }) })),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ToggleField, { label: "Register cartridge as Steam library", description: "Only needed if a cartridge carries its own Steam library folder. Edits Steam's libraryfolders.vdf directly \u2014 leave off unless you need it.", checked: config.register_library, onChange: (checked) => update({ register_library: checked }) })),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: refreshDrives }, "Rescan drives")),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: () => clearKnownGames() }, "Forget tracked games")),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: () => debugListDrives().then(setDiagnostics) }, "Diagnose drive detection")),
        diagnostics && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement("div", { style: { fontSize: "11px", whiteSpace: "pre-wrap" } }, diagnostics.length === 0
                ? "No /dev/-backed mounts found at all."
                : diagnostics
                    .map((d) => `${d.mountpoint}\n  block=${d.block} removable_flag=${d.removable_flag} usb=${d.is_usb} media_path=${d.media_convention}\n  → treated as removable: ${d.treated_as_removable}`)
                    .join("\n\n")))),
        saving && window.SP_REACT.createElement(DFL.PanelSectionRow, null, "Saving\u2026"),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement("div", { style: { fontSize: "12px", opacity: 0.6, marginTop: "8px" } },
                "Detected drives: ",
                drives.length ? drives.join(", ") : "none right now"))));
}
var index = definePlugin(() => {
    return {
        name: "PHYsteam",
        titleView: window.SP_REACT.createElement("div", { className: DFL.staticClasses.Title }, "PHYsteam"),
        content: window.SP_REACT.createElement(Content, null),
        icon: window.SP_REACT.createElement(FaCompactDisc, null),
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
