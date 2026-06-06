// Frontend/src/utils/request.js
import axios from "axios";
import { message as AntMessage } from "antd";
import { translations } from "../i18n/translations.js";

const baseURL = import.meta.env.DEV ? "/api" : "";

const getLang = () => {
  try {
    const saved = window.localStorage.getItem("lang") || "";
    return saved.toLowerCase().startsWith("en") ? "en" : "zh";
  } catch {
    return "zh";
  }
};

const instance = axios.create({ baseURL, timeout: 100000 });

instance.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error),
);

instance.interceptors.response.use(
  (response) => response,
  (error) => {
    const http = translations[getLang()]?.http || translations.zh.http;

    if (error?.response) {
      const code = error.response.status;
      error.message = http.status[code] || `${http.connectionError} ${code}`;
      if (code === 404) window.location.href = "/NotFound";
    } else if (JSON.stringify(error).includes("timeout")) {
      error.message = http.timeout;
    } else {
      error.message = http.networkFail;
    }

    if (!error.config?._suppressToast) AntMessage.error(error.message);
    return Promise.reject(error);
  },
);

export default instance;
