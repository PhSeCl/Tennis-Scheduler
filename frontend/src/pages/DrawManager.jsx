import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "../contexts/LanguageContext.jsx";
import { getAvailableFiles, readJsonFile, writeJsonFile } from "../services/eelBridge";

const normalizeEntries = (payload) => {
  if (!Array.isArray(payload)) {
    return [];
  }
  return payload;
};

const isPowerOfTwo = (n) => n > 0 && (n & (n - 1)) === 0;

const isDoublesEvent = (filePath) => {
  const base = filePath.split("/").pop() || "";
  const stem = base.replace(/\.json$/i, "").toLowerCase();
  if (["md", "wd", "xd"].includes(stem)) {
    return true;
  }
  return stem.includes("double");
};

function DrawManager() {
  const { lang, t } = useTranslation();
  const [availableDraws, setAvailableDraws] = useState([]);
  const [eventType, setEventType] = useState("");
  const [entries, setEntries] = useState([]);
  const [nameA, setNameA] = useState("");
  const [nameB, setNameB] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const loadDrawFiles = async () => {
      try {
        const files = await getAvailableFiles();
        const drawFiles = (Array.isArray(files) ? files : [])
          .filter((file) => file.startsWith("matches/"))
          .filter((file) => file.endsWith(".json"));
        if (isMounted) {
          setAvailableDraws(drawFiles);
          setEventType(drawFiles[0] || "");
        }
      } catch (error) {
        if (isMounted) {
          setAvailableDraws([]);
          setEventType("");
        }
      }
    };

    loadDrawFiles();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadDraw = async () => {
      if (!eventType) {
        if (isMounted) {
          setEntries([]);
        }
        return;
      }
      setLoading(true);
      try {
        const data = await readJsonFile(eventType);
        if (isMounted) {
          setEntries(normalizeEntries(data));
        }
      } catch (error) {
        if (isMounted) {
          setEntries([]);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadDraw();
    return () => {
      isMounted = false;
    };
  }, [eventType]);

  const doubles = useMemo(() => isDoublesEvent(eventType), [eventType]);

  const handleAddEntry = () => {
    if (!nameA.trim()) {
      alert("Please enter at least one player name.");
      return;
    }

    if (doubles) {
      if (!nameB.trim()) {
        alert("Please enter two player names for doubles.");
        return;
      }
      setEntries((prev) => [...prev, { players: [nameA.trim(), nameB.trim()] }]);
    } else {
      setEntries((prev) => [...prev, { player: nameA.trim() }]);
    }

    setNameA("");
    setNameB("");
  };

  const handleAddBye = () => {
    if (doubles) {
      setEntries((prev) => [...prev, { players: ["轮空"] }]);
    } else {
      setEntries((prev) => [...prev, { player: "轮空" }]);
    }
  };

  const handleRemove = (index) => {
    setEntries((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSave = async () => {
    try {
      if (!isPowerOfTwo(entries.length)) {
        const nextPower = 2 ** Math.ceil(Math.log2(entries.length || 1));
        const missing = nextPower - entries.length;
        alert(
          `Save Failed: The total number of entries must be a power of 2 (e.g., 8, 16, 32, 64). You currently have ${entries.length} entries. Please add Bye (\u8f6e\u7a7a) to fill the gaps.`
        );
        return;
      }
      await writeJsonFile(eventType, entries);
      alert("Draw saved successfully.");
    } catch (error) {
      alert(error?.message || "Save failed.");
    }
  };

  const rounds = useMemo(() => {
    const totalLeafSlots = 2 ** Math.ceil(Math.log2(Math.max(entries.length || 2, 2)));
    const paddedEntries = [
      ...entries,
      ...Array.from({ length: totalLeafSlots - entries.length }, () => null)
    ];
    const roundList = [];

    const leafMatches = [];
    for (let i = 0; i < paddedEntries.length; i += 2) {
      leafMatches.push({
        slots: [
          { entry: paddedEntries[i], absoluteIndex: i < entries.length ? i : null },
          { entry: paddedEntries[i + 1], absoluteIndex: i + 1 < entries.length ? i + 1 : null }
        ]
      });
    }
    roundList.push(leafMatches);

    while (roundList[roundList.length - 1].length > 1) {
      const prevRound = roundList[roundList.length - 1];
      const nextRound = [];
      for (let i = 0; i < prevRound.length; i += 2) {
        nextRound.push({ slots: [] });
      }
      roundList.push(nextRound);
    }

    return roundList;
  }, [entries]);

  const getRoundLabel = (matchCount) => {
    if (lang === "zh") {
      if (matchCount === 1) {
        return "决赛";
      }
      if (matchCount === 2) {
        return "半决赛";
      }
      if (matchCount === 4) {
        return "四分之一决赛";
      }
      if (matchCount === 8) {
        return "十六强";
      }
      if (matchCount === 16) {
        return "三十二强";
      }
      return `前${matchCount * 2}`;
    }
    if (matchCount === 1) {
      return "Final";
    }
    if (matchCount === 2) {
      return "Semifinals";
    }
    if (matchCount === 4) {
      return "Quarterfinals";
    }
    if (matchCount === 8) {
      return "Round of 16";
    }
    if (matchCount === 16) {
      return "Round of 32";
    }
    return `Round of ${matchCount * 2}`;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{t("drawManagement")}</h1>
          <p className="text-sm text-slate-500 mt-1">{t("drawManagementDesc")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className={`text-sm ${isPowerOfTwo(entries.length) ? "text-slate-500" : "text-rose-600"}`}>
            {`${t("currentEntries")}: ${entries.length}`}
            {!isPowerOfTwo(entries.length) && entries.length > 0 && (
              ` (${t("needsMoreByes")}: ${
                2 ** Math.ceil(Math.log2(entries.length || 1)) - entries.length
              } / ${2 ** Math.ceil(Math.log2(entries.length || 1))})`
            )}
          </div>
          <select
            value={eventType}
            onChange={(event) => setEventType(event.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            disabled={availableDraws.length === 0}
          >
            {availableDraws.length === 0 && (
              <option value="">{t("noEntries")}</option>
            )}
            {availableDraws.map((file) => (
              <option key={file} value={file}>
                {file.replace(/^matches\//, "").replace(/\.json$/i, "")}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleSave}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-800"
          >
            {t("saveDraw")}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <label className="text-sm font-medium text-slate-600">{t("playerName")}</label>
            <input
              type="text"
              value={nameA}
              onChange={(event) => setNameA(event.target.value)}
              placeholder={doubles ? t("playerName") : t("playerName")}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>
          {doubles && (
            <div className="flex-1">
              <label className="text-sm font-medium text-slate-600">{t("partner")}</label>
              <input
                type="text"
                value={nameB}
                onChange={(event) => setNameB(event.target.value)}
                placeholder={t("partner")}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
              />
            </div>
          )}
          <button
            type="button"
            onClick={handleAddEntry}
            className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500"
          >
            {t("addEntry")}
          </button>
          <button
            type="button"
            onClick={handleAddBye}
            className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            {t("addBye")}
          </button>
        </div>
      </div>

      <div className="flex items-stretch gap-12 overflow-x-auto pb-8 min-w-max p-4 bg-slate-50/50 rounded-xl border border-slate-200">
        {rounds.map((round, roundIdx) => (
          <div key={`round-${roundIdx}`} className="flex flex-col justify-around gap-4 w-64 shrink-0">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {getRoundLabel(round.length)}
            </div>
            {round.map((match, matchIdx) => {
              if (roundIdx > 0) {
                return (
                  <div
                    key={`round-${roundIdx}-match-${matchIdx}`}
                    className="rounded-xl border border-dashed border-slate-200 bg-slate-100 px-4 py-6 text-center text-sm text-slate-400"
                  >
                    {t("winnerAdvances")}
                  </div>
                );
              }

              return (
                <div
                  key={`round-${roundIdx}-match-${matchIdx}`}
                  className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3"
                >
                  {match.slots.map((slot, slotIdx) => {
                    const entry = slot.entry;
                    const label = entry
                      ? entry.players
                        ? entry.players.join(" / ")
                        : entry.player
                      : t("emptySlot");
                    return (
                      <div key={`slot-${matchIdx}-${slotIdx}`} className="flex items-center justify-between">
                        <span className={entry ? "text-slate-900 font-medium" : "text-slate-400"}>
                          {label}
                        </span>
                        {entry && slot.absoluteIndex !== null && (
                          <button
                            type="button"
                            onClick={() => handleRemove(slot.absoluteIndex)}
                            className="text-xs text-rose-600 hover:text-rose-500"
                          >
                            {t("remove")}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {!loading && entries.length === 0 && (
        <div className="text-center text-slate-400 py-10">{t("noEntries")}</div>
      )}
    </div>
  );
}

export default DrawManager;
