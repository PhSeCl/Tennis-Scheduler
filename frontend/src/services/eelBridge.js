const getEel = () => {
  if (!window.eel) {
    throw new Error("Eel bridge is not available. Is the backend running?");
  }
  return window.eel;
};

const callEel = async (fn, ...args) => {
  try {
    const eel = getEel();
    return await fn(...args)();
  } catch (error) {
    console.error("[Eel Bridge Error]:", error);
    throw new Error(error?.message || "Eel call failed");
  }
};

export const getAvailableFiles = async () => {
  return callEel(getEel().get_available_files);
};

export const readJsonFile = async (filename) => {
  return callEel(getEel().read_json_file, filename);
};

export const writeJsonFile = async (filename, data) => {
  return callEel(getEel().write_json_file, filename, data);
};

export const runScheduler = async (config, filePaths) => {
  return callEel(getEel().run_scheduler, config, filePaths);
};

export const exportScheduleToTxt = async (scheduleData, selectedDraws) => {
  return callEel(getEel().export_schedule_to_txt, scheduleData, selectedDraws);
};
