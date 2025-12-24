import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag, Select, Space, Alert, Empty, Spin, Typography, Drawer, Descriptions } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { LogEvent } from '../api/types';

const { Option } = Select;
const { Text } = Typography;

const PRIORITY_COLORS: Record<string, string> = {
  'Critical': 'red',
  'Error': 'volcano',
  'Warning': 'orange',
  'Notice': 'gold',
  'Info': 'blue',
  'Debug': 'default'
};

const Logs: React.FC = () => {
  // 1. Fetch Active Containers
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEvent | null>(null);

  // Auto-select first container
  useEffect(() => {
    if (containers && containers.length > 0 && !selectedContainerId) {
      setSelectedContainerId(containers[0].id);
    }
  }, [containers, selectedContainerId]);

  // 2. Fetch Logs for selected container
  const { 
    data: logsData, 
    isLoading, 
    error 
  } = useQuery({
    queryKey: ['logs', selectedContainerId],
    queryFn: () => selectedContainerId 
      ? api.getContainerLogs(selectedContainerId) 
      : Promise.reject('No container selected'),
    enabled: !!selectedContainerId,
    // Polling is disabled for now as historical logs might not change frequently 
    // without a real storage backend or real-time stream.
    refetchInterval: 5000 
  });

  const columns: ColumnsType<LogEvent> = [
    {
      title: 'Time',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 200,
      render: (ts) => new Date(ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority) => (
        <Tag color={PRIORITY_COLORS[priority] || 'default'}>
          {priority ? priority.toUpperCase() : 'UNKNOWN'}
        </Tag>
      ),
    },
    {
      title: 'Rule',
      dataIndex: 'rule',
      key: 'rule',
      width: 150,
      render: (text) => <b>{text}</b>,
    },
    {
      title: 'Output',
      dataIndex: 'output',
      key: 'output',
      render: (text) => (
        <Text code style={{ display: 'block', maxWidth: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {text}
        </Text>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <a onClick={() => {
          setSelectedLog(record);
          setDrawerVisible(true);
        }}>Details</a>
      ),
    },
  ];

  if (!containers || containers.length === 0) {
    return (
      <Card title="Container Logs">
        <Empty description="No active containers found" />
      </Card>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        
        {/* Container Selector */}
        <Card>
          <Space>
            <span>Container:</span>
            <Select
              style={{ width: 300 }}
              value={selectedContainerId}
              onChange={setSelectedContainerId}
              placeholder="Select a container"
            >
              {containers.map(c => (
                <Option key={c.id} value={c.id}>{c.name}</Option>
              ))}
            </Select>
          </Space>
        </Card>

        {/* Logs Table */}
        <Card 
          title={
            <Space>
              <FileTextOutlined />
              <span>Security Events Log</span>
            </Space>
          }
        >
          {error && (
             <Alert 
               message="Error loading logs" 
               description="Could not fetch logs. Ensure backend service is running." 
               type="error" 
               showIcon 
               style={{ marginBottom: 16 }}
             />
          )}

          {logsData?.warning && (
            <Alert
                message="Note"
                description={logsData.warning}
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
            />
          )}

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" tip="Loading logs..." />
            </div>
          ) : (
            <Table 
              dataSource={logsData?.logs || []} 
              columns={columns} 
              rowKey={(record, index) => `${record.timestamp}-${index}`}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1000 }}
              locale={{ emptyText: 'No logs available for this container' }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedLog(record);
                  setDrawerVisible(true);
                },
                style: { cursor: 'pointer' }
              })}
            />
          )}
        </Card>

        <Drawer
          title="Log Details"
          placement="right"
          width={600}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
        >
          {selectedLog && (
            <Descriptions column={1} bordered>
              <Descriptions.Item label="Time">
                {new Date(selectedLog.timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
              </Descriptions.Item>
              <Descriptions.Item label="Priority">
                <Tag color={PRIORITY_COLORS[selectedLog.priority] || 'default'}>
                  {selectedLog.priority ? selectedLog.priority.toUpperCase() : 'UNKNOWN'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Rule">{selectedLog.rule}</Descriptions.Item>
              <Descriptions.Item label="Source">{selectedLog.source}</Descriptions.Item>
              <Descriptions.Item label="Tags">
                {selectedLog.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}
              </Descriptions.Item>
              <Descriptions.Item label="Output">
                <Text code>{selectedLog.output}</Text>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Drawer>
      </Space>
    </div>
  );
};

export default Logs;
