import { useEffect, useMemo, useState } from "react";
import { Calendar, Download, Play, Settings } from "lucide-react";
import { useTranslation } from "../contexts/LanguageContext.jsx";
import { exportScheduleToTxt, getAvailableFiles, runScheduler } from "../services/eelBridge";

const defaultConfig = {
  courts: 5,
  beam_width: 10,
  w1: 10.0,
  w2: 7.0,
  w3: 2.5
};

const numberField = (value) => (value === "" ? "" : Number(value));

function SchedulerConsole() {
  const { t } = useTranslation();
  const [config, setConfig] = useState(defaultConfig);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [availableDraws, setAvailableDraws] = useState([]);
  const [selectedDraws, setSelectedDraws] = useState([]);

  useEffect(() => {
    let isMounted = true;
    const loadDrawFiles = async () => {
      try {
        const files = await getAvailableFiles();
        const validDraws = (Array.isArray(files) ? files : [])
          .filter((file) => file.startsWith("matches/"))
          .filter((file) => file.endsWith(".json"));
        if (isMounted) {
          setAvailableDraws(validDraws);
          setSelectedDraws(validDraws);
        }
      } catch (err) {
        if (isMounted) {
          setAvailableDraws([]);
          setSelectedDraws([]);
        }
      }
    };

    loadDrawFiles();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleConfigChange = (field, value) => {
    setConfig((prev) => ({
      ...prev,
      [field]: numberField(value)
    }));
  };

  const handleRunScheduler = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      if (selectedDraws.length === 0) {
        setError("Please select at least one event to schedule.");
        setLoading(false);
        return;
      }
      const payload = {
        players: "players.json",
        draws: selectedDraws
      };

      const response = await runScheduler(config, payload);
      if (response?.status === "success") {
        setResult(response);
      } else {
        setError(response?.message || "Scheduler failed.");
      }
    } catch (err) {
      setError(err?.message || "Scheduler failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await exportScheduleToTxt(result, selectedDraws);
      if (response?.status === "success") {
        alert(`Successfully exported to: ${response.filepath}`);
      } else {
        alert(response?.message || "Export failed.");
      }
    } catch (err) {
      alert(err?.message || "Export failed.");
    }
  };

  const scheduleSlots = useMemo(() => {
    if (!result?.schedule_by_t) {
      return [];
    }
    return Object.keys(result.schedule_by_t)
      .sort((a, b) => Number(a) - Number(b))
      .map((slot) => ({
        slot,
        matches: result.schedule_by_t[slot] || []
      }));
  }, [result]);

  const toggleDrawSelection = (file) => {
    setSelectedDraws((prev) =>
      prev.includes(file) ? prev.filter((item) => item !== file) : [...prev, file]
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{t("schedulerConsole")}</h1>
          <p className="text-sm text-slate-500 mt-1">{t("schedulerConsoleDesc")}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 space-y-5">
          <div className="flex items-center gap-2 text-slate-700">
            <Settings className="h-5 w-5" />
            <h2 className="text-lg font-semibold">{t("configuration")}</h2>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-400">{t("eventsToSchedule")}</p>
              <div className="space-y-2">
                {availableDraws.length === 0 && (
                  <p className="text-sm text-slate-400">{t("noEntries")}</p>
                )}
                {availableDraws.map((file) => (
                  <label key={file} className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={selectedDraws.includes(file)}
                      onChange={() => toggleDrawSelection(file)}
                      className="h-4 w-4 rounded border-slate-300"
                    />
                    <span className="font-medium text-slate-700">
                      {file.replace(/^matches\//, "").replace(/\.json$/i, "")}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-400">{t("baseSettings")}</p>
              <div className="space-y-3">
                <label className="flex flex-col text-sm text-slate-600">
                  {t("courts")}
                  <input
                    type="number"
                    min="1"
                    value={config.courts}
                    onChange={(event) => handleConfigChange("courts", event.target.value)}
                    className="mt-1 rounded-lg border border-slate-200 px-3 py-2"
                  />
                </label>
                <label className="flex flex-col text-sm text-slate-600">
                  {t("beamWidth")}
                  <input
                    type="number"
                    min="1"
                    value={config.beam_width}
                    onChange={(event) => handleConfigChange("beam_width", event.target.value)}
                    className="mt-1 rounded-lg border border-slate-200 px-3 py-2"
                  />
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-400">{t("penaltyWeights")}</p>
              <div className="space-y-3">
                <label className="flex flex-col text-sm text-slate-600">
                  {t("earlyStartPenalty")}
                  <input
                    type="number"
                    step="0.1"
                    value={config.w1}
                    onChange={(event) => handleConfigChange("w1", event.target.value)}
                    className="mt-1 rounded-lg border border-slate-200 px-3 py-2"
                  />
                </label>
                <label className="flex flex-col text-sm text-slate-600">
                  {t("backToBackPenalty")}
                  <input
                    type="number"
                    step="0.1"
                    value={config.w2}
                    onChange={(event) => handleConfigChange("w2", event.target.value)}
                    className="mt-1 rounded-lg border border-slate-200 px-3 py-2"
                  />
                </label>
                <label className="flex flex-col text-sm text-slate-600">
                  {t("emptyCourtPenalty")}
                  <input
                    type="number"
                    step="0.1"
                    value={config.w3}
                    onChange={(event) => handleConfigChange("w3", event.target.value)}
                    className="mt-1 rounded-lg border border-slate-200 px-3 py-2"
                  />
                </label>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={handleRunScheduler}
            disabled={loading}
            className={`w-full flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-white transition ${
              loading ? "bg-slate-400" : "bg-emerald-600 hover:bg-emerald-500"
            }`}
          >
            <Play className="h-4 w-4" />
            {loading ? t("runScheduler") + "..." : t("runScheduler")}
          </button>
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {error}
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-700">
            <Calendar className="h-5 w-5" />
            <h2 className="text-lg font-semibold">{t("timetable")}</h2>
          </div>

          {!result && (
            <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-8 text-center text-slate-400">
              {t("runToView")}
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="grid gap-3 sm:grid-cols-2">
                <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-400">{t("totalPenaltyCost")}</p>
                  <p className="text-2xl font-semibold text-slate-900 mt-2">{result.total_cost ?? "-"}</p>
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-400">{t("totalTimeSlots")}</p>
                  <p className="text-2xl font-semibold text-slate-900 mt-2">{result.total_slots ?? "-"}</p>
                </div>
                </div>
                <button
                  type="button"
                  onClick={handleExport}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <Download className="h-4 w-4" />
                  {t("exportToTxt")}
                </button>
              </div>

              <div className="space-y-4">
                {scheduleSlots.map((slot) => (
                  <div key={slot.slot} className="bg-slate-50/50 border border-slate-200 rounded-2xl p-4">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
                      {t("slot")} {slot.slot}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4 w-full">
                      {slot.matches.map((match, idx) => (
                        <div
                          key={`${slot.slot}-${match.match_id}`}
                          className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow"
                        >
                          <div className="flex items-center justify-between">
                            <span className="px-2 py-1 bg-emerald-50 text-emerald-700 text-[10px] font-bold uppercase rounded-md tracking-wider">
                              {t("court")} {idx + 1}
                            </span>
                            <span className="text-slate-400 text-xs">ID: {match.match_id}</span>
                          </div>
                          <div className="mt-3">
                            <h3 className="text-slate-900 font-semibold text-sm leading-snug">
                              {match.label}
                            </h3>
                            {Array.isArray(match.players) && match.players.length > 0 && (
                              <p className="text-slate-500 text-xs mt-1.5">
                                {match.players.join(" / ")}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default SchedulerConsole;
