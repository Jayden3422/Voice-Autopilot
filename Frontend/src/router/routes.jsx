import { Navigate } from "react-router-dom";
import Home from "../pages/Home";
import Record from "../pages/Record";

const routes = [
  {
    path: "/",
    element: <Navigate to="/home" replace />
  },
  {
    path: "/home",
    element: <Home />,
    label: "Home",
  },
  {
    path: "/record",
    element: <Record />,
    label: "Record"
  },
  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
];

export default routes;