import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
  ButtonItem,
  Dropdown,
  DropdownOption,
  Field,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { useEffect, useState } from "react";
import { FaCompactDisc } from "react-icons/fa";

interface Config {
  mode: "auto" | "fixed";
  drive: string | null;
  require_card: boolean;
  register_library: boolean;
  dry_run: boolean;
}

const getConfig = callable<[], Config>("get_config");
const saveConfig = callable<[Config], boolean>("save_config");
const listDrives = callable<[], string[]>("list_removable_drives");
const clearKnownGames = callable<[], boolean>("clear_known_games");
const debugListDrives = callable<[], any[]>("debug_list_drives");

function Content() {
  const [config, setConfig] = useState<Config | null>(null);
  const [drives, setDrives] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [diagnostics, setDiagnostics] = useState<any[] | null>(null);

  const refreshDrives = () => {
    listDrives().then(setDrives).catch(() => setDrives([]));
  };

  useEffect(() => {
    getConfig().then(setConfig);
    refreshDrives();
    const interval = setInterval(refreshDrives, 3000);
    return () => clearInterval(interval);
  }, []);

  if (!config) {
    return (
      <PanelSection>
        <PanelSectionRow>Loading PHYsteam config…</PanelSectionRow>
      </PanelSection>
    );
  }

  const update = async (patch: Partial<Config>) => {
    const next = { ...config, ...patch };
    setConfig(next);
    setSaving(true);
    try {
      await saveConfig(next);
    } finally {
      setSaving(false);
    }
  };

  const driveOptions: DropdownOption[] = [
    { data: "__auto__", label: "Auto-detect last removable drive" },
    ...drives.map((d) => ({ data: d, label: d })),
  ];

  return (
    <PanelSection title="PHYsteam">
      <PanelSectionRow>
        <Field label="Mode" description="Auto-detect watches every removable drive. Fixed watches one specific drive.">
          <Dropdown
            rgOptions={[
              { data: "auto", label: "Auto-detect" },
              { data: "fixed", label: "Fixed drive" },
            ]}
            selectedOption={config.mode}
            onChange={(o) => update({ mode: o.data })}
          />
        </Field>
      </PanelSectionRow>

      {config.mode === "fixed" && (
        <PanelSectionRow>
          <Field label="Drive">
            <Dropdown
              rgOptions={driveOptions}
              selectedOption={config.drive ?? "__auto__"}
              onChange={(o) => update({ drive: o.data === "__auto__" ? null : o.data })}
            />
          </Field>
        </PanelSectionRow>
      )}

      <PanelSectionRow>
        <ToggleField
          label="Require cartridge"
          description="Force-close a tracked game if its drive is removed or missing at launch."
          checked={config.require_card}
          onChange={(checked) => update({ require_card: checked })}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Dry run (log only, don't launch)"
          description="Detects cartridges and logs what it would do, but never actually launches a game. Use this to test insert/remove detection safely."
          checked={config.dry_run}
          onChange={(checked) => update({ dry_run: checked })}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Register cartridge as Steam library"
          description="Only needed if a cartridge carries its own Steam library folder. Edits Steam's libraryfolders.vdf directly — leave off unless you need it."
          checked={config.register_library}
          onChange={(checked) => update({ register_library: checked })}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem layout="below" onClick={refreshDrives}>
          Rescan drives
        </ButtonItem>
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => clearKnownGames()}>
          Forget tracked games
        </ButtonItem>
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => debugListDrives().then(setDiagnostics)}
        >
          Diagnose drive detection
        </ButtonItem>
      </PanelSectionRow>

      {diagnostics && (
        <PanelSectionRow>
          <div style={{ fontSize: "11px", whiteSpace: "pre-wrap" }}>
            {diagnostics.length === 0
              ? "No /dev/-backed mounts found at all."
              : diagnostics
                  .map(
                    (d) =>
                      `${d.mountpoint}\n  block=${d.block} removable_flag=${d.removable_flag} usb=${d.is_usb} media_path=${d.media_convention}\n  → treated as removable: ${d.treated_as_removable}`
                  )
                  .join("\n\n")}
          </div>
        </PanelSectionRow>
      )}

      {saving && <PanelSectionRow>Saving…</PanelSectionRow>}

      <PanelSectionRow>
        <div style={{ fontSize: "12px", opacity: 0.6, marginTop: "8px" }}>
          Detected drives: {drives.length ? drives.join(", ") : "none right now"}
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
}

export default definePlugin(() => {
  return {
    name: "PHYsteam",
    titleView: <div className={staticClasses.Title}>PHYsteam</div>,
    content: <Content />,
    icon: <FaCompactDisc />,
  };
});
