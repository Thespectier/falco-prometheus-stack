import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Select, Space, Alert, Spin, Typography, Drawer, Descriptions, Tag } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { ContainerSummary, Incident } from '../api/types';

const { Option } = Select;
const { Text } = Typography;

/** 时间窗选项：秒数 → 展示文案；0 表示不限窗口 */
const WINDOW_OPTIONS = [
  { value: 300, label: '5m' },
  { value: 900, label: '15m' },
  { value: 1800, label: '30m' },
  { value: 0, label: 'All Time' },
];

/** 后端返回的时间戳按东八区展示（与后端入库时的偏移口径一致） */
function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
}

/** 威胁分数配色：>80 红、>50 橙、其余绿 */
function threatColor(score: number): string {
  if (score > 80) return 'red';
  if (score > 50) return 'orange';
  return 'green';
}

/** 表格列定义；"Details" 列要打开抽屉，由调用方注入回调 */
function buildColumns(openDetails: (record: Incident) => void): ColumnsType<Incident> {
  return [
    { title: 'Time', dataIndex: 'timestamp', key: 'timestamp', render: (ts) => formatTimestamp(ts) },
    { title: 'Container', dataIndex: 'container_id', key: 'container_id' },
    { title: 'Threat Score', dataIndex: 'threat_score', key: 'threat_score', render: (score) => score.toFixed(2) },
    { title: 'Attribute', dataIndex: 'attribute_name', key: 'attribute_name' },
    { title: 'Value', dataIndex: 'attribute_value', key: 'attribute_value' },
    { title: 'Event Type', dataIndex: 'event_type', key: 'event_type' },
    { title: 'Process', dataIndex: 'process_name', key: 'process_name' },
    { title: 'AI Analysis', dataIndex: 'analysis', key: 'analysis', render: (text) => text || <Text type="secondary" italic>Pending...</Text> },
    {
      title: 'Details',
      dataIndex: 'details',
      key: 'details',
      render: (text) => (
        <Text code style={{ display: 'block', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {text}
        </Text>
      )
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <a onClick={() => openDetails(record)}>Details</a>
      ),
    },
  ];
}

/** 容器与时间窗筛选条 */
const IncidentFilters: React.FC<{
  containers?: ContainerSummary[];
  containerId?: string;
  onContainerChange: (id: string | undefined) => void;
  windowSeconds: number;
  onWindowChange: (seconds: number) => void;
}> = ({ containers, containerId, onContainerChange, windowSeconds, onWindowChange }) => (
  <Card>
    <Space wrap>
      <Space>
        <span>Container:</span>
        <Select
          style={{ width: 250 }}
          value={containerId}
          onChange={onContainerChange}
          placeholder="All Containers"
          allowClear
        >
          {containers?.map(c => (
            <Option key={c.id} value={c.id}>{c.name}</Option>
          ))}
        </Select>
      </Space>

      <Space>
        <span>Window:</span>
        <Select
          style={{ width: 140 }}
          value={windowSeconds}
          onChange={onWindowChange}
        >
          {WINDOW_OPTIONS.map(option => (
            <Option key={option.value} value={option.value}>{option.label}</Option>
          ))}
        </Select>
      </Space>
    </Space>
  </Card>
);

/** 事件详情抽屉 */
const IncidentDrawer: React.FC<{
  incident: Incident | null;
  visible: boolean;
  onClose: () => void;
}> = ({ incident, visible, onClose }) => (
  <Drawer
    title="Incident Details"
    placement="right"
    width={600}
    onClose={onClose}
    open={visible}
  >
    {incident && (
      <Descriptions column={1} bordered>
        <Descriptions.Item label="Container">{incident.container_id}</Descriptions.Item>
        <Descriptions.Item label="Time">{formatTimestamp(incident.timestamp)}</Descriptions.Item>
        <Descriptions.Item label="Threat Score">
          <Tag color={threatColor(incident.threat_score)}>
            {incident.threat_score.toFixed(2)}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Attribute">{incident.attribute_name}</Descriptions.Item>
        <Descriptions.Item label="Value">{incident.attribute_value}</Descriptions.Item>
        <Descriptions.Item label="Event Type">{incident.event_type}</Descriptions.Item>
        <Descriptions.Item label="Process">{incident.process_name}</Descriptions.Item>
        <Descriptions.Item label="AI Analysis">
          <Text type={incident.analysis ? undefined : "secondary"} italic={!incident.analysis}>
            {incident.analysis || "Analysis pending..."}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="Details">
          <Text code>{incident.details}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Alert Content">
          <Text code>{incident.alert_content}</Text>
        </Descriptions.Item>
      </Descriptions>
    )}
  </Drawer>
);

const Incidents: React.FC = () => {
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | undefined>(undefined);
  const [windowSeconds, setWindowSeconds] = useState<number>(0);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  const {
    data: incidents,
    isLoading,
    error
  } = useQuery({
    queryKey: ['incidents', selectedContainerId, windowSeconds],
    queryFn: () => api.getIncidents(selectedContainerId, windowSeconds),
    refetchInterval: 10000
  });

  const openDetails = (record: Incident) => {
    setSelectedIncident(record);
    setDrawerVisible(true);
  };

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <IncidentFilters
          containers={containers}
          containerId={selectedContainerId}
          onContainerChange={setSelectedContainerId}
          windowSeconds={windowSeconds}
          onWindowChange={setWindowSeconds}
        />

        <Card
          title={
            <Space>
              <SafetyCertificateOutlined style={{ color: '#ff4d4f' }} />
              <span>Security Incidents</span>
            </Space>
          }
        >
          {error && (
             <Alert
               message="Error loading incidents"
               description="Could not fetch incidents."
               type="error"
               showIcon
               style={{ marginBottom: 16 }}
             />
          )}

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" tip="Loading incidents..." />
            </div>
          ) : (
            <Table
              dataSource={incidents || []}
              columns={buildColumns(openDetails)}
              rowKey={(record) => `${record.container_id}-${record.timestamp}-${record.event_type}`}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1200 }}
              onRow={(record) => ({
                onClick: () => openDetails(record),
                style: { cursor: 'pointer' }
              })}
            />
          )}
        </Card>

        <IncidentDrawer
          incident={selectedIncident}
          visible={drawerVisible}
          onClose={() => setDrawerVisible(false)}
        />
      </Space>
    </div>
  );
};

export default Incidents;
