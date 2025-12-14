import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag, Select, Space, Alert, Empty, Spin } from 'antd';
import { WarningOutlined, FilterOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { AlertStat } from '../api/types';

const { Option } = Select;

const PRIORITY_COLORS: Record<string, string> = {
  'Critical': 'red',
  'Error': 'volcano',
  'Warning': 'orange',
  'Notice': 'gold',
  'Info': 'blue',
  'Debug': 'default'
};

const Alerts: React.FC = () => {
  // 1. Fetch Active Containers to populate selector
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined);

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
    queryKey: ['alerts', selectedContainerId, priorityFilter],
    queryFn: () => selectedContainerId 
      ? api.getContainerAlerts(selectedContainerId, priorityFilter) 
      : Promise.reject('No container selected'),
    enabled: !!selectedContainerId,
    refetchInterval: 10000
  });

  const columns: ColumnsType<AlertStat> = [
    {
      title: 'Rule',
      dataIndex: 'rule',
      key: 'rule',
      render: (text) => <b>{text}</b>,
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority) => (
        <Tag color={PRIORITY_COLORS[priority] || 'default'}>
          {priority.toUpperCase()}
        </Tag>
      ),
      sorter: (a, b) => {
        const priorities = ['Critical', 'Error', 'Warning', 'Notice', 'Info', 'Debug'];
        return priorities.indexOf(a.priority) - priorities.indexOf(b.priority);
      },
    },
    {
      title: 'Rate (Last 5m)',
      dataIndex: 'rate',
      key: 'rate',
      render: (rate) => `${rate.toFixed(4)} alerts/sec`,
      sorter: (a, b) => a.rate - b.rate,
      defaultSortOrder: 'descend'
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
              <FilterOutlined />
              <span>Priority:</span>
              <Select
                style={{ width: 150 }}
                value={priorityFilter}
                onChange={setPriorityFilter}
                allowClear
                placeholder="All Priorities"
              >
                {Object.keys(PRIORITY_COLORS).map(p => (
                  <Option key={p} value={p}>
                    <Tag color={PRIORITY_COLORS[p]}>{p}</Tag>
                  </Option>
                ))}
              </Select>
            </Space>
          </Space>
        </Card>

        {/* Alerts Table */}
        <Card 
          title={
            <Space>
              <WarningOutlined style={{ color: '#faad14' }} />
              <span>Alert Statistics (Real-time)</span>
            </Space>
          }
          extra={alertsData?.note && <Tag color="blue">{alertsData.note}</Tag>}
        >
          {error && (
             <Alert 
               message="Error loading alerts" 
               description="Could not fetch alert statistics. Ensure Prometheus is running." 
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
              dataSource={alertsData?.alerts_stats || []} 
              columns={columns} 
              rowKey={(record) => `${record.rule}-${record.priority}`}
              pagination={{ pageSize: 10 }}
              locale={{ emptyText: 'No alerts detected in the last 5 minutes' }}
            />
          )}
        </Card>
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
