import React, { createContext, useContext, useState } from "react";

const dictionary = {
  zh: {
    players: "选手管理",
    draws: "抽签管理",
    scheduler: "排表控制台",
    playerManagement: "选手管理",
    playerManagementDesc: "管理选手档案及驻地状态。",
    saveChanges: "保存更改",
    playerName: "选手姓名",
    gender: "性别",
    events: "参赛项目",
    stayingAtVenue: "是否驻地",
    addPlayer: "添加选手",
    totalPlayers: "总人数",
    actions: "操作",
    delete: "删除",
    male: "男",
    female: "女",
    drawManagement: "抽签管理",
    drawManagementDesc: "管理赛事抽签及对阵名单。",
    currentEntries: "当前人数",
    needsMoreByes: "还需轮空数",
    saveDraw: "保存抽签",
    partner: "搭档",
    addEntry: "添加报名",
    addBye: "添加轮空",
    matchup: "对阵",
    remove: "移除",
    emptySlot: "(空位)",
    winnerAdvances: "胜者晋级",
    schedulerConsole: "排表控制台",
    schedulerConsoleDesc: "配置智能调度参数并预览赛程。",
    configuration: "排表配置",
    eventsToSchedule: "排表项目",
    baseSettings: "基础参数",
    courts: "可用场地数",
    beamWidth: "搜索宽度",
    penaltyWeights: "惩罚权重",
    earlyStartPenalty: "早场非驻地惩罚 (w1)",
    backToBackPenalty: "连场休息惩罚 (w2)",
    emptyCourtPenalty: "空场浪费惩罚 (w3)",
    runScheduler: "一键智能排表",
    timetable: "赛程课表",
    totalPenaltyCost: "总惩罚分",
    totalTimeSlots: "预计总时间片",
    exportToTxt: "导出 TXT",
    court: "场地",
    slot: "时间片",
    noEntries: "暂无数据，请在上方添加。",
    runToView: "请点击左侧按钮生成智能赛程。"
  },
  en: {
    players: "Players",
    draws: "Draws",
    scheduler: "Scheduler",
    playerManagement: "Player Management",
    playerManagementDesc: "Manage player profiles and lodging status.",
    saveChanges: "Save Changes",
    playerName: "Player Name",
    gender: "Gender",
    events: "Events",
    stayingAtVenue: "Staying at Venue",
    addPlayer: "Add Player",
    totalPlayers: "Total players",
    actions: "Actions",
    delete: "Delete",
    male: "Male",
    female: "Female",
    drawManagement: "Draw Management",
    drawManagementDesc: "Manage draw entries and matchup pairs.",
    currentEntries: "Current Entries",
    needsMoreByes: "needs Byes",
    saveDraw: "Save Draw",
    partner: "Partner",
    addEntry: "Add Entry",
    addBye: "Add Bye",
    matchup: "Matchup",
    remove: "Remove",
    emptySlot: "(Empty Slot)",
    winnerAdvances: "Winner advances",
    schedulerConsole: "Scheduler Console",
    schedulerConsoleDesc: "Configure the smart scheduler and review the timetable.",
    configuration: "Configuration",
    eventsToSchedule: "Events to Schedule",
    baseSettings: "Base Settings",
    courts: "Courts",
    beamWidth: "Beam Width",
    penaltyWeights: "Penalty Weights",
    earlyStartPenalty: "Early Start Penalty (w1)",
    backToBackPenalty: "Back-to-Back Rest Penalty (w2)",
    emptyCourtPenalty: "Empty Court Penalty (w3)",
    runScheduler: "Run Smart Scheduler",
    timetable: "Timetable",
    totalPenaltyCost: "TOTAL PENALTY COST",
    totalTimeSlots: "TOTAL TIME SLOTS",
    exportToTxt: "Export to TXT",
    court: "COURT",
    slot: "SLOT",
    noEntries: "No entries yet. Add one above.",
    runToView: "Run the scheduler to view the timetable."
  }
};

const LanguageContext = createContext();

export const LanguageProvider = ({ children }) => {
  const [lang, setLang] = useState("zh");
  const t = (key) => dictionary[lang][key] || key;
  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => useContext(LanguageContext);
