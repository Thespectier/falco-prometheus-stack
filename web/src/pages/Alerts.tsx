import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Select, Space, Alert, Empty, Spin, Typography, Drawer, Descriptions } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { ContainerSummary } from '../api/types';

const { Option } = Select;

const { Text } = Typography;

/** 时间窗选项：秒数 → 展示文案；0 表示不限窗口 */
const WINDOW_OPTIONS = [
  { value: 300, label: '5m' },
  { value: 900, label: '15m' },
  { value: 1800, label: '30m' },
  { value: 0, label: 'All Time' },
];

/** 复选框占位：用 emoji 而不是 antd 图标，保持与既有界面一致 */
const ContainerOutlinedWrapper = () => {
  return <span style={{ marginRight: 8 }}>📦</span>;
};

/** 表格列定义；"Details" 列要打开抽屉，由调用方注入回调 */
function buildColumns(openDetails: (record: any) => void): ColumnsType<any> {
  return [
    { title: 'Container', dataIndex: 'container_id', key: 'container_id' },
    { title: 'Time', dataIndex: 'timestamp', key: 'timestamp', render: (ts) => new Date(ts).toLocaleString() },
    { title: 'Category', dataIndex: 'category', key: 'category' },
    { title: 'Reason', dataIndex: 'reason', key: 'reason' },
    { title: 'Attribute Value', dataIndex: 'attribute_value', key: 'attribute_value' },
    { title: 'Event Type', dataIndex: 'evt_type', key: 'evt_type' },
    { title: 'Process', dataIndex: 'proc_name', key: 'proc_name' },
    { title: 'FD Name', dataIndex: 'fd_name', key: 'fd_name' },
    {
      title: 'Output',
      dataIndex: 'output',
      key: 'output',
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
const AlertFilters: React.FC<{
  containers: ContainerSummary[];
  containerId: string;
  onContainerChange: (id: string) => void;
  windowSeconds: number;
  onWindowChange: (seconds: number) => void;
}> = ({ containers, containerId, onContainerChange, windowSeconds, onWindowChange }) => (
  <Card>
    <Space wrap>
      <Space>
        <ContainerOutlinedWrapper />
        <span>Container:</span>
        <Select
          style={{ width: 250 }}
          value={containerId}
          onChange={onContainerChange}
          placeholder="Select a container"
        >
          {containers.map(c => (
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

/** 告警详情抽屉 */
const AlertDrawer: React.FC<{
  alert: any | null;
  visible: boolean;
  onClose: () => void;
}> = ({ alert, visible, onClose }) => (
  <Drawer
    title="Alert Details"
    placement="right"
    width={600}
    onClose={onClose}
    open={visible}
  >
    {alert && (
      <Descriptions column={1} bordered>
        <Descriptions.Item label="Container">{alert.container_id}</Descriptions.Item>
        <Descriptions.Item label="Time">{new Date(alert.timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</Descriptions.Item>
        <Descriptions.Item label="Category">{alert.category}</Descriptions.Item>
        <Descriptions.Item label="Reason">{alert.reason}</Descriptions.Item>
        <Descriptions.Item label="Attribute Value">{alert.attribute_value}</Descriptions.Item>
        <Descriptions.Item label="Event Type">{alert.evt_type}</Descriptions.Item>
        <Descriptions.Item label="Process">{alert.proc_name}</Descriptions.Item>
        <Descriptions.Item label="FD Name">{alert.fd_name}</Descriptions.Item>
        <Descriptions.Item label="Output">
          <Text code>{alert.output}</Text>
        </Descriptions.Item>
      </Descriptions>
    )}
  </Drawer>
);

const Alerts: React.FC = () => {
  // 容器列表用于筛选下拉；默认 "all" 表示不限容器
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string>('all');
  const [windowSeconds, setWindowSeconds] = useState<number>(0);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<any | null>(null);

  // 选定容器与时间窗后拉告警，10 秒一轮
  const {
    data: alertsData,
    isLoading,
    error
  } = useQuery({
    queryKey: ['alerts', selectedContainerId, windowSeconds],
    queryFn: () => api.getContainerAlerts(selectedContainerId, windowSeconds),
    refetchInterval: 10000
  });

  const openDetails = (record: any) => {
    setSelectedAlert(record);
    setDrawerVisible(true);
  };

  if (!containers || containers.length === 0) {
    return (
      <Card title="Container Security Alerts">
        <Empty description="No active containers found" />
      </Card>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>

        <AlertFilters
          containers={containers}
          containerId={selectedContainerId}
          onContainerChange={setSelectedContainerId}
          windowSeconds={windowSeconds}
          onWindowChange={setWindowSeconds}
        />

          <Card 
            title={
              <Space>
                <WarningOutlined style={{ color: '#faad14' }} />
              <span>Alert Details</span>
              </Space>
            }
          extra={null}
        >
          {error && (
             <Alert 
               message="Error loading alerts" 
               description="Could not fetch alert details. Ensure API and alerts ingestor are running." 
               type="error" 
               showIcon 
               style={{ marginBottom: 16 }}
             />
          )}

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" tip="Loading alerts data..." />
            </div>
          ) : (
            <Table 
              dataSource={alertsData?.alerts || []} 
              columns={buildColumns(openDetails)} 
              rowKey={(record) => `${record.container_id}-${record.timestamp}-${record.evt_type}-${record.proc_name}-${record.fd_name}`}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1200 }}
              locale={{ emptyText: windowSeconds && windowSeconds > 0 ? 'No alerts detected in selected window' : 'No alerts detected' }}
              onRow={(record) => ({
                onClick: () => openDetails(record),
                style: { cursor: 'pointer' }
              })}
            />
          )}
        </Card>

        <AlertDrawer
          alert={selectedAlert}
          visible={drawerVisible}
          onClose={() => setDrawerVisible(false)}
        />
      </Space>
    </div>
  );
};

export default Alerts;
