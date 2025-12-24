import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Select, Space, Alert, Empty, Spin, Typography, Drawer, Descriptions } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';

const { Option } = Select;

const { Text } = Typography;

const Alerts: React.FC = () => {
  // 1. Fetch Active Containers to populate selector
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(null);
  const [windowSeconds, setWindowSeconds] = useState<number>(300);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<any | null>(null);

  // Auto-select first container
  useEffect(() => {
    if (containers && containers.length > 0 && !selectedContainerId) {
      setSelectedContainerId(containers[0].id);
    }
  }, [containers, selectedContainerId]);

  // 2. Fetch Alerts for selected container
  const { 
    data: alertsData, 
    isLoading, 
    error 
  } = useQuery({
    queryKey: ['alerts', selectedContainerId, windowSeconds],
    queryFn: () => selectedContainerId 
      ? api.getContainerAlerts(selectedContainerId!, windowSeconds) 
      : Promise.reject('No container selected'),
    enabled: !!selectedContainerId,
    refetchInterval: 10000
  });

  const columns: ColumnsType<any> = [
    { title: 'Container', dataIndex: 'container_id', key: 'container_id' },
    { title: 'Time', dataIndex: 'timestamp', key: 'timestamp', render: (ts) => new Date(ts).toLocaleString() },
    { title: 'Category', dataIndex: 'category', key: 'category' },
    { title: 'Reason', dataIndex: 'reason', key: 'reason' },
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
        <a onClick={() => {
          setSelectedAlert(record);
          setDrawerVisible(true);
        }}>Details</a>
      ),
    },
  ];

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
        
        {/* Filter Bar */}
        <Card>
          <Space wrap>
            <Space>
              <ContainerOutlinedWrapper />
              <span>Container:</span>
              <Select
                style={{ width: 250 }}
                value={selectedContainerId}
                onChange={setSelectedContainerId}
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
                onChange={setWindowSeconds}
              >
                <Option value={300}>5m</Option>
                <Option value={900}>15m</Option>
                <Option value={1800}>30m</Option>
                <Option value={0}>All Time</Option>
              </Select>
            </Space>
          </Space>
        </Card>

        {/* Alerts Table */}
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
              columns={columns} 
              rowKey={(record) => `${record.container_id}-${record.timestamp}-${record.evt_type}-${record.proc_name}-${record.fd_name}`}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1200 }}
              locale={{ emptyText: windowSeconds && windowSeconds > 0 ? 'No alerts detected in selected window' : 'No alerts detected' }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedAlert(record);
                  setDrawerVisible(true);
                },
                style: { cursor: 'pointer' }
              })}
            />
          )}
        </Card>

        <Drawer
          title="Alert Details"
          placement="right"
          width={600}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
        >
          {selectedAlert && (
            <Descriptions column={1} bordered>
              <Descriptions.Item label="Container">{selectedAlert.container_id}</Descriptions.Item>
              <Descriptions.Item label="Time">{new Date(selectedAlert.timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</Descriptions.Item>
              <Descriptions.Item label="Category">{selectedAlert.category}</Descriptions.Item>
              <Descriptions.Item label="Reason">{selectedAlert.reason}</Descriptions.Item>
              <Descriptions.Item label="Event Type">{selectedAlert.evt_type}</Descriptions.Item>
              <Descriptions.Item label="Process">{selectedAlert.proc_name}</Descriptions.Item>
              <Descriptions.Item label="FD Name">{selectedAlert.fd_name}</Descriptions.Item>
              <Descriptions.Item label="Output">
                <Text code>{selectedAlert.output}</Text>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Drawer>
      </Space>
    </div>
  );
};

// Helper component to avoid icon import issues if any
const ContainerOutlinedWrapper = () => {
    // We can use a simple span or import icon if needed. 
    // Since we used icons before, let's try to be consistent but minimal.
    return <span style={{ marginRight: 8 }}>📦</span>; 
};

export default Alerts;
