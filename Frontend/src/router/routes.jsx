import { Navigate } from "react-router-dom";
import Home from "../pages/Home";
import Record from "../pages/Record";
import Autopilot from "../pages/Autopilot";
import Settings from "../pages/Settings";

const routes = [
  {
    path: "/",
    element: <Navigate to="/home" replace />
  },
  {
    path: "/home",
    element: <Home />,
    labelKey: "nav.home",
  },
  {
    path: "/autopilot",
    element: <Autopilot />,
    labelKey: "nav.autopilot",
  },
  {
    path: "/record",
    element: <Record />,
    labelKey: "nav.record"
  },
  {
    path: "/settings",
    element: <Settings />,
    labelKey: "nav.settings",
  },
  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
];

export default routes;
