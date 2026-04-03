import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import { useTranslation } from "../contexts/LanguageContext.jsx";
import { readJsonFile, writeJsonFile } from "../services/eelBridge";

const normalizePlayers = (payload) => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {};
  }
  return payload;
};

function PlayerManager() {
  const { t } = useTranslation();
  const [players, setPlayers] = useState({});
  const [newName, setNewName] = useState("");
  const [newEvents, setNewEvents] = useState("");
  const [newSex, setNewSex] = useState("男");
  const [newStaying, setNewStaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const loadPlayers = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await readJsonFile("players.json");
        if (isMounted) {
          setPlayers(normalizePlayers(data));
        }
      } catch (err) {
        console.error(err);
        if (isMounted) {
          setPlayers({});
          setError(err?.message || "Failed to load players.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadPlayers();
    return () => {
      isMounted = false;
    };
  }, []);

  const sortedEntries = useMemo(() => {
    return Object.entries(players).sort(([a], [b]) => a.localeCompare(b));
  }, [players]);

  const handleToggle = (name) => {
    setPlayers((prev) => ({
      ...prev,
      [name]: {
        ...(prev[name] || {}),
        is_staying_at_venue: !prev[name]?.is_staying_at_venue
      }
    }));
  };

  const handleDelete = (name) => {
    setPlayers((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const handleAdd = () => {
    const trimmed = newName.trim();
    if (!trimmed) {
      alert("Please enter a player name.");
      return;
    }
    const eventsArray = newEvents
      .split(",")
      .map((event) => event.trim())
      .filter(Boolean)
      .map((event) => ({ event_type: event }));
    setPlayers((prev) => ({
      ...prev,
      [trimmed]: {
        ...(prev[trimmed] || {}),
        name: trimmed,
        sex: newSex,
        is_staying_at_venue: newStaying,
        registered_events: eventsArray
      }
    }));
    setNewName("");
    setNewEvents("");
    setNewSex("男");
    setNewStaying(false);
  };

  const handleSave = async () => {
    try {
      await writeJsonFile("players.json", players);
      alert("Saved successfully.");
    } catch (error) {
      alert(error?.message || "Save failed.");
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{t("playerManagement")}</h1>
          <p className="text-sm text-slate-500 mt-1">{t("playerManagementDesc")}</p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          className="px-4 py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-800"
        >
          {t("saveChanges")}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <label className="text-sm font-medium text-slate-600">{t("playerName")}</label>
            <input
              type="text"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder={t("playerName")}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>
          <div className="w-32">
            <label className="text-sm font-medium text-slate-600">{t("gender")}</label>
            <select
              value={newSex}
              onChange={(event) => setNewSex(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="男">{t("male")}</option>
              <option value="女">{t("female")}</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium text-slate-600">{t("events")}</label>
            <input
              type="text"
              value={newEvents}
              onChange={(event) => setNewEvents(event.target.value)}
              placeholder={t("events")}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={newStaying}
              onChange={(event) => setNewStaying(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            {t("stayingAtVenue")}
          </label>
          <button
            type="button"
            onClick={handleAdd}
            className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500"
          >
            {t("addPlayer")}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 text-sm font-medium text-slate-600">
          {error
            ? "Error loading players"
            : loading
              ? "Loading players..."
              : `${t("totalPlayers")}: ${sortedEntries.length}`}
        </div>
        {error && (
          <div className="px-4 py-3 text-sm text-rose-600 bg-rose-50 border-b border-rose-100">
            Error: {error}
          </div>
        )}
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium w-1/4">{t("playerName")}</th>
              <th className="px-4 py-2 font-medium w-2/5">{t("events")}</th>
              <th className="px-4 py-2 font-medium w-1/5">{t("stayingAtVenue")}</th>
              <th className="px-4 py-2 font-medium w-1/5">{t("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {sortedEntries.map(([name, info]) => (
              <tr key={name} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <span
                    className={`px-2.5 py-1 text-sm font-medium border rounded-md ${
                      info?.sex === "男"
                        ? "bg-blue-50 text-blue-700 border-blue-200"
                        : info?.sex === "女"
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : "bg-slate-50 text-slate-700 border-slate-200"
                    }`}
                  >
                    {name}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {Array.isArray(info?.registered_events) && info.registered_events.length > 0 ? (
                      info.registered_events.map((evt, idx) => (
                        <span
                          key={`${name}-event-${idx}`}
                          className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 rounded-md"
                        >
                          {evt?.event_type}
                          {evt?.partner && (
                            <span className="opacity-70 text-[10px] ml-1">({evt.partner})</span>
                          )}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={Boolean(info?.is_staying_at_venue)}
                    onChange={() => handleToggle(name)}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => handleDelete(name)}
                    className="inline-flex items-center gap-1 text-rose-600 hover:text-rose-500"
                  >
                    <Trash2 className="h-4 w-4" />
                    {t("delete")}
                  </button>
                </td>
              </tr>
            ))}
            {!loading && sortedEntries.length === 0 && (
              <tr>
                <td className="px-4 py-6 text-center text-slate-400" colSpan={4}>
                  {t("noEntries")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PlayerManager;
