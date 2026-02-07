import { useState, useEffect } from "react";
import {
  Table,
  Button,
  Drawer,
  Tag,
  Space,
  Typography,
  Collapse,
  Empty,
  message as AntMessage,
  Descriptions,
  Segmented,
  Tooltip,
} from "antd";
import { EyeOutlined, RedoOutlined } from "@ant-design/icons";
import { useI18n } from "../../i18n/LanguageContext.jsx";
import * as api from "../../utils/api";
import "./index.scss";

const { Title, Text, Paragraph } = Typography;

const Record = () => {
  const { t } = useI18n();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedRun, setSelectedRun] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [runTypeFilter, setRunTypeFilter] = useState("all");
  const limit = 20;

  useEffect(() => {
    loadRecords(true);
  }, [runTypeFilter]);

  const loadRecords = async (reset = false) => {
    setLoading(true);
    try {
      const currentOffset = reset ? 0 : offset;
      const params = {
        limit,
        offset: currentOffset,
      };
      if (runTypeFilter !== "all") {
        params.run_type = runTypeFilter;
      }
      const res = await api.getAPI("/autopilot/runs", params);
      const data = res?.data || res || {};
      const newRecords = data.runs || [];

      if (reset) {
        setRecords(newRecords);
        setOffset(limit);
      } else {
        setRecords([...records, ...newRecords]);
        setOffset(currentOffset + limit);
      }

      setHasMore(newRecords.length === limit);
    } catch (err) {
      console.error("Failed to load records:", err);
      AntMessage.error("Failed to load records");
    } finally {
      setLoading(false);
    }
  };

  const viewDetails = async (runId) => {
    setDrawerVisible(true);
    setLoadingDetail(true);
    setSelectedRun(null);
    try {
      const res = await api.getAPI(`/autopilot/runs/${runId}`);
      setSelectedRun(res?.data || res || null);
    } catch (err) {
      console.error("Failed to load run details:", err);
      AntMessage.error("Failed to load details");
      setDrawerVisible(false);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRetry = async (runId) => {
    setRetrying(true);
    try {
      const res = await api.postAPI(`/autopilot/retry/${runId}`);
      const data = res?.data || res || {};

      AntMessage.success(t("record.retrySuccess"));

      // Refresh the current run details
      const updatedRun = await api.getAPI(`/autopilot/runs/${runId}`);
      setSelectedRun(updatedRun?.data || updatedRun || null);

      // Refresh the list
      loadRecords(true);
    } catch (err) {
      console.error("Failed to retry:", err);
      AntMessage.error(t("record.retryFailed"));
    } finally {
      setRetrying(false);
    }
  };

  const getStatusTag = (status) => {
    const statusMap = {
      pending: { color: "default", label: t("record.statusPending") },
      transcribed: { color: "processing", label: t("record.statusTranscribed") },
      extracted: { color: "processing", label: t("record.statusExtracted") },
      drafted: { color: "processing", label: t("record.statusDrafted") },
      previewed: { color: "cyan", label: t("record.statusPreviewed") },
      executed: { color: "success", label: t("record.statusExecuted") },
      conflict: { color: "warning", label: t("record.statusConflict") },
      error: { color: "error", label: t("record.statusError") },
    };
    const config = statusMap[status] || { color: "default", label: status };
    return <Tag color={config.color}>{config.label}</Tag>;
  };

  const getRunTypeTag = (type) => {
    const typeMap = {
      autopilot: { color: "purple", label: t("record.runTypeAutopilot") },
      voice_schedule: { color: "geekblue", label: t("record.runTypeVoiceSchedule") },
    };
    const config = typeMap[type] || { color: "default", label: type };
    return <Tag color={config.color}>{config.label}</Tag>;
  };

  const getInputTypeTag = (type) => {
    const typeMap = {
      audio: { color: "blue", label: t("record.inputTypeAudio") },
      text: { color: "green", label: t("record.inputTypeText") },
    };
    const config = typeMap[type] || { color: "default", label: type };
    return <Tag color={config.color}>{config.label}</Tag>;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const columns = [
    {
      title: t("record.runId"),
      dataIndex: "run_id",
      key: "run_id",
      width: 280,
      render: (text) => (
        <Text copyable style={{ fontSize: "12px", fontFamily: "monospace" }}>
          {text}
        </Text>
      ),
    },
    {
      title: t("record.createdAt"),
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: formatDate,
    },
    {
      title: t("record.runType"),
      dataIndex: "run_type",
      key: "run_type",
      width: 120,
      render: getRunTypeTag,
    },
    {
      title: t("record.inputType"),
      dataIndex: "input_type",
      key: "input_type",
      width: 100,
      render: getInputTypeTag,
    },
    {
      title: t("record.status"),
      dataIndex: "status",
      key: "status",
      width: 120,
      render: getStatusTag,
    },
    {
      title: t("record.actions"),
      key: "actions",
      width: 120,
      render: (_, record) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => viewDetails(record.run_id)}
        >
          {t("record.viewDetails")}
        </Button>
      ),
    },
  ];

  const renderJsonCollapse = (title, data) => {
    if (!data) {
      return (
        <Collapse.Panel header={title} key={title}>
          <Text type="secondary">{t("record.noData")}</Text>
        </Collapse.Panel>
      );
    }

    return (
      <Collapse.Panel header={title} key={title}>
        <pre
          style={{
            background: "#f5f5f5",
            padding: "12px",
            borderRadius: "4px",
            overflow: "auto",
            maxHeight: "400px",
          }}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      </Collapse.Panel>
    );
  };

  return (
    <div className="record-page">
      <div className="record-header">
        <Title level={2}>{t("record.title")}</Title>
        <Button onClick={() => loadRecords(true)} loading={loading}>
          {t("record.refresh")}
        </Button>
      </div>

      <div className="record-filter">
        <Segmented
          value={runTypeFilter}
          onChange={setRunTypeFilter}
          options={[
            { label: t("record.runTypeAll"), value: "all" },
            { label: t("record.runTypeAutopilot"), value: "autopilot" },
            { label: t("record.runTypeVoiceSchedule"), value: "voice_schedule" },
          ]}
        />
      </div>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="run_id"
        loading={loading}
        pagination={false}
        locale={{
          emptyText: <Empty description={t("record.noRecords")} />,
        }}
      />

      {hasMore && records.length > 0 && (
        <div style={{ textAlign: "center", marginTop: "16px" }}>
          <Button onClick={() => loadRecords(false)} loading={loading}>
            {t("record.loadMore")}
          </Button>
        </div>
      )}

      <Drawer
        title={t("record.details")}
        placement="right"
        width={800}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        loading={loadingDetail}
        extra={
          selectedRun &&
          (selectedRun.status === "error" || selectedRun.status === "conflict") &&
          selectedRun.run_type === "autopilot" && (
            <Tooltip title={t("record.retryHint")}>
              <Button
                type="primary"
                icon={<RedoOutlined />}
                onClick={() => handleRetry(selectedRun.run_id)}
                loading={retrying}
              >
                {t("record.retry")}
              </Button>
            </Tooltip>
          )
        }
      >
        {selectedRun && (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            {/* Basic Info */}
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label={t("record.runId")}>
                <Text copyable style={{ fontFamily: "monospace", fontSize: "12px" }}>
                  {selectedRun.run_id}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t("record.createdAt")}>
                {formatDate(selectedRun.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label={t("record.runType")}>
                {getRunTypeTag(selectedRun.run_type)}
              </Descriptions.Item>
              <Descriptions.Item label={t("record.inputType")}>
                {getInputTypeTag(selectedRun.input_type)}
              </Descriptions.Item>
              <Descriptions.Item label={t("record.status")}>
                {getStatusTag(selectedRun.status)}
              </Descriptions.Item>
            </Descriptions>

            {/* Error Message */}
            {selectedRun.error && (
              <div>
                <Title level={5}>{t("record.error")}</Title>
                <Paragraph
                  style={{
                    background: "#fff2e8",
                    border: "1px solid #ffbb96",
                    padding: "12px",
                    borderRadius: "4px",
                  }}
                >
                  {selectedRun.error}
                </Paragraph>
              </div>
            )}

            {/* Transcript */}
            {selectedRun.transcript && (
              <div>
                <Title level={5}>{t("record.transcript")}</Title>
                <div
                  style={{
                    background: "#f5f5f5",
                    padding: "12px",
                    borderRadius: "4px",
                  }}
                >
                  {selectedRun.transcript.split("\n---\n").map((segment, index) => (
                    <div key={index}>
                      {index > 0 && (
                        <div
                          style={{
                            borderTop: "2px dashed #d9d9d9",
                            margin: "12px 0",
                          }}
                        />
                      )}
                      <Paragraph
                        style={{
                          margin: 0,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {index > 0 && (
                          <Text type="secondary" style={{ fontSize: "12px" }}>
                            {t("record.followUp")} {index}:{" "}
                          </Text>
                        )}
                        {segment}
                      </Paragraph>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Collapsible Sections */}
            <Collapse defaultActiveKey={[]}>
              {renderJsonCollapse(
                t("record.extractedData"),
                selectedRun.extracted_json
              )}
              {renderJsonCollapse(t("record.evidence"), selectedRun.evidence_json)}
              {renderJsonCollapse(t("record.replyDraft"), selectedRun.reply_draft)}
              {renderJsonCollapse(t("record.actionPlan"), selectedRun.actions_json)}
            </Collapse>

            {/* Raw Input (for debugging) */}
            {selectedRun.raw_input && (
              <Collapse>
                <Collapse.Panel header={t("record.rawInput")} key="raw">
                  <Paragraph
                    style={{
                      background: "#f5f5f5",
                      padding: "12px",
                      borderRadius: "4px",
                      maxHeight: "200px",
                      overflow: "auto",
                      fontSize: "12px",
                      fontFamily: "monospace",
                      wordBreak: "break-all",
                    }}
                  >
                    {selectedRun.raw_input}
                  </Paragraph>
                </Collapse.Panel>
              </Collapse>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  );
};

export default Record;
