import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Radio,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { CopyOutlined, LinkOutlined } from "@ant-design/icons";
import { useI18n } from "../../i18n/useI18n.js";
import { getAPI, postAPI, putAPI } from "../../utils/api";
import "./index.scss";

const { Title, Text } = Typography;

async function fetchSettings() {
  const res = await getAPI("/settings");
  return res.data;
}

async function saveSettings(body) {
  const res = await putAPI("/settings", body);
  return res.data;
}

async function fetchGcStatus() {
  try {
    const res = await getAPI("/settings/google-calendar/status", undefined, { _suppressToast: true });
    return res.data;
  } catch {
    return { has_credentials: false, is_connected: false };
  }
}

async function fetchAuthUrl() {
  const res = await getAPI("/settings/google-calendar/auth-url");
  return res.data.auth_url;
}

async function disconnectGoogle() {
  await postAPI("/settings/google-calendar/disconnect");
}

export default function Settings() {
  const { t } = useI18n();
  const s = (k) => t(`settings.${k}`);

  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [gcStatus, setGcStatus] = useState({ has_credentials: false, is_connected: false });
  const [gcConnecting, setGcConnecting] = useState(false);
  const [gcDisconnecting, setGcDisconnecting] = useState(false);
  const [calendarMode, setCalendarMode] = useState("playwright");

  // Handle OAuth callback query params
  useEffect(() => {
    const connected = searchParams.get("gc_connected");
    const err = searchParams.get("gc_error");
    if (connected) {
      message.success(s("googleConnected"));
      refreshGcStatus();
      setSearchParams({}, { replace: true });
    } else if (err) {
      message.error(`OAuth error: ${err}`);
      setSearchParams({}, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshGcStatus = useCallback(async () => {
    const st = await fetchGcStatus();
    setGcStatus(st);
  }, []);

  // Initial load
  useEffect(() => {
    (async () => {
      try {
        const data = await fetchSettings();
        form.setFieldsValue(flattenSettings(data));
        setCalendarMode(data?.calendar?.mode ?? "playwright");
        await refreshGcStatus();
      } catch {
        message.error(s("saveError"));
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Flatten nested settings into form fields
  function flattenSettings(data) {
    const c = data?.connectors ?? {};
    const ga = data?.calendar?.google_api ?? {};
    return {
      slack_enabled: c.slack?.enabled ?? false,
      slack_webhook_url: c.slack?.webhook_url ?? "",
      email_enabled: c.email?.enabled ?? false,
      smtp_host: c.email?.smtp_host ?? "",
      smtp_port: c.email?.smtp_port ?? 587,
      smtp_user: c.email?.smtp_user ?? "",
      smtp_pass: c.email?.smtp_pass ?? "",
      smtp_from: c.email?.smtp_from ?? "",
      smtp_from_name: c.email?.smtp_from_name ?? "",
      smtp_ssl: c.email?.smtp_ssl ?? false,
      smtp_timeout: c.email?.smtp_timeout ?? 30,
      linear_enabled: c.linear?.enabled ?? false,
      linear_api_key: c.linear?.api_key ?? "",
      linear_team_id: c.linear?.team_id ?? "",
      gc_client_id: ga.client_id ?? "",
      gc_client_secret: ga.client_secret ?? "",
      gc_redirect_uri: ga.redirect_uri ?? "http://localhost:8888/settings/google-calendar/callback",
      gc_calendar_id: ga.calendar_id ?? "primary",
    };
  }

  // Unflatten form values back to nested structure
  function unflattenValues(vals) {
    return {
      connectors: {
        slack: {
          enabled: vals.slack_enabled,
          webhook_url: vals.slack_webhook_url,
        },
        email: {
          enabled: vals.email_enabled,
          smtp_host: vals.smtp_host,
          smtp_port: vals.smtp_port,
          smtp_user: vals.smtp_user,
          smtp_pass: vals.smtp_pass,
          smtp_from: vals.smtp_from,
          smtp_from_name: vals.smtp_from_name,
          smtp_ssl: vals.smtp_ssl,
          smtp_timeout: vals.smtp_timeout,
        },
        linear: {
          enabled: vals.linear_enabled,
          api_key: vals.linear_api_key,
          team_id: vals.linear_team_id,
        },
      },
      calendar: {
        mode: calendarMode,
        google_api: {
          client_id: vals.gc_client_id,
          client_secret: vals.gc_client_secret,
          redirect_uri: vals.gc_redirect_uri,
          calendar_id: vals.gc_calendar_id,
        },
      },
    };
  }

  const handleSave = async () => {
    try {
      const vals = await form.validateFields();
      setSaving(true);
      await saveSettings(unflattenValues(vals));
      message.success(s("saved"));
      await refreshGcStatus();
    } catch (e) {
      if (e?.errorFields) return; // form validation error — already shown
      // interceptor already showed the HTTP error toast
    } finally {
      setSaving(false);
    }
  };

  const handleConnect = async () => {
    // Save credentials first
    try {
      const vals = form.getFieldsValue();
      await saveSettings(unflattenValues(vals));
    } catch {
      // Saving credentials is best-effort; the auth URL request reports actionable errors.
    }

    setGcConnecting(true);
    try {
      const url = await fetchAuthUrl();
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      const detail = e?.response?.data?.error;
      if (detail) message.error(detail); // show backend-specific error on top of interceptor's generic one
    } finally {
      setGcConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setGcDisconnecting(true);
    try {
      await disconnectGoogle();
      message.success(s("googleNotConnected"));
      await refreshGcStatus();
    } catch {
      // interceptor already showed the HTTP error toast
    } finally {
      setGcDisconnecting(false);
    }
  };

  const redirectUri = form.getFieldValue("gc_redirect_uri") ||
    "http://localhost:8888/settings/google-calendar/callback";

  const slackEnabled = Form.useWatch("slack_enabled", form);
  const emailEnabled = Form.useWatch("email_enabled", form);
  const linearEnabled = Form.useWatch("linear_enabled", form);

  return (
    <div className="settings-page">
      <Title level={3}>{s("title")}</Title>
      <Form form={form} layout="vertical" requiredMark={false}>

        {/* ── Connectors ────────────────────────────────────────────── */}
        <Title level={4}>{s("connectors")}</Title>

        {/* Slack */}
        <Card className="settings-card">
          <div className="connector-header">
            <span className="connector-title">{s("slack.title")}</span>
            <Form.Item name="slack_enabled" valuePropName="checked" noStyle>
              <Switch />
            </Form.Item>
          </div>
          {slackEnabled && (
            <Form.Item name="slack_webhook_url" label={s("slack.webhookUrl")} className="settings-field">
              <Input.Password placeholder="https://hooks.slack.com/services/..." visibilityToggle />
            </Form.Item>
          )}
        </Card>

        {/* Email */}
        <Card className="settings-card">
          <div className="connector-header">
            <span className="connector-title">{s("email.title")}</span>
            <Form.Item name="email_enabled" valuePropName="checked" noStyle>
              <Switch />
            </Form.Item>
          </div>
          {emailEnabled && (
            <div className="connector-fields">
              <div className="field-row">
                <Form.Item name="smtp_host" label={s("email.smtpHost")} className="field-grow">
                  <Input placeholder="smtp.gmail.com" />
                </Form.Item>
                <Form.Item name="smtp_port" label={s("email.smtpPort")} className="field-port">
                  <InputNumber min={1} max={65535} />
                </Form.Item>
                <Form.Item name="smtp_ssl" label={s("email.smtpSsl")} valuePropName="checked" className="field-ssl">
                  <Switch />
                </Form.Item>
              </div>
              <div className="field-row">
                <Form.Item name="smtp_user" label={s("email.smtpUser")} className="field-grow">
                  <Input placeholder="you@example.com" />
                </Form.Item>
                <Form.Item name="smtp_pass" label={s("email.smtpPass")} className="field-grow">
                  <Input.Password visibilityToggle />
                </Form.Item>
              </div>
              <div className="field-row">
                <Form.Item name="smtp_from" label={s("email.smtpFrom")} className="field-grow">
                  <Input placeholder="noreply@example.com" />
                </Form.Item>
                <Form.Item name="smtp_from_name" label={s("email.smtpFromName")} className="field-grow">
                  <Input placeholder="Voice Autopilot" />
                </Form.Item>
              </div>
            </div>
          )}
        </Card>

        {/* Linear */}
        <Card className="settings-card">
          <div className="connector-header">
            <span className="connector-title">{s("linear.title")}</span>
            <Form.Item name="linear_enabled" valuePropName="checked" noStyle>
              <Switch />
            </Form.Item>
          </div>
          {linearEnabled && (
            <div className="connector-fields">
              <Form.Item name="linear_api_key" label={s("linear.apiKey")} className="settings-field">
                <Input.Password placeholder="lin_api_..." visibilityToggle />
              </Form.Item>
              <Form.Item name="linear_team_id" label={s("linear.teamId")} className="settings-field">
                <Input placeholder="team-uuid" />
              </Form.Item>
            </div>
          )}
        </Card>

        <Divider />

        {/* ── Calendar ──────────────────────────────────────────────── */}
        <Title level={4}>{s("calendarSection")}</Title>
        <Card className="settings-card">
          <div className="calendar-mode-row">
            <Text strong>{s("calendarMode")}</Text>
            <Radio.Group
              value={calendarMode}
              onChange={(e) => setCalendarMode(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              style={{ marginLeft: 16 }}
            >
              <Radio.Button value="playwright">{s("playwright")}</Radio.Button>
              <Radio.Button value="api">{s("googleApi")}</Radio.Button>
            </Radio.Group>
          </div>

          {calendarMode === "api" && (
            <div className="gc-api-config">
              <Alert
                message={s("googleConnectHint")}
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />

              <div className="field-row">
                <Form.Item name="gc_client_id" label={s("googleApiConfig.clientId")} className="field-grow">
                  <Input placeholder="xxx.apps.googleusercontent.com" />
                </Form.Item>
                <Form.Item name="gc_client_secret" label={s("googleApiConfig.clientSecret")} className="field-grow">
                  <Input.Password visibilityToggle />
                </Form.Item>
              </div>

              <Form.Item name="gc_redirect_uri" label={s("googleApiConfig.redirectUri")}>
                <Input
                  readOnly
                  suffix={
                    <Tooltip title="Copy">
                      <CopyOutlined
                        style={{ cursor: "pointer" }}
                        onClick={() => {
                          navigator.clipboard.writeText(redirectUri);
                          message.success("Copied");
                        }}
                      />
                    </Tooltip>
                  }
                />
              </Form.Item>
              <Alert
                message={
                  <span>
                    {s("googleRedirectHint")}{" "}
                    <Text code>{redirectUri}</Text>
                  </span>
                }
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
              />

              <Form.Item name="gc_calendar_id" label={s("googleApiConfig.calendarId")}>
                <Input placeholder="primary" />
              </Form.Item>

              <div className="gc-connect-row">
                <div className="gc-status">
                  {gcStatus.is_connected ? (
                    <Tag color="success">{s("googleConnected")}</Tag>
                  ) : (
                    <Tag color="default">{s("googleNotConnected")}</Tag>
                  )}
                </div>
                {gcStatus.is_connected ? (
                  <Button danger loading={gcDisconnecting} onClick={handleDisconnect}>
                    {s("disconnectGoogle")}
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<LinkOutlined />}
                    loading={gcConnecting}
                    onClick={handleConnect}
                  >
                    {s("connectGoogle")}
                  </Button>
                )}
              </div>
            </div>
          )}
        </Card>

        <Divider />

        <Button type="primary" size="large" loading={saving} onClick={handleSave}>
          {s("save")}
        </Button>
      </Form>
    </div>
  );
}
