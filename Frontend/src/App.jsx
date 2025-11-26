import { Routes, Route, Link, useLocation } from "react-router-dom";
import routes from "./router/routes";
import { Menu } from "antd";

const App = () => {
  const location = useLocation();

  const items = routes
    .filter(r => r.label)
    .map(route => ({
      key: route.path,
      label: <Link to={route.path}>{route.label}</Link>,
    }));

  return (
    <div className="app-root">
      <header className="header">
        <Menu
          mode="horizontal"
          items={items}
          selectedKeys={[location.pathname]}
        />
      </header>

      <main className="content">
        <Routes>
          {routes.map(route => (
            <Route
              key={route.path}
              path={route.path}
              element={route.element}
            />
          ))}
        </Routes>
      </main>
    </div>
  );
};

export default App;