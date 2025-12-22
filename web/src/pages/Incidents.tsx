import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Select, Space, Alert, Spin, Typography, Drawer, Descriptions, Tag } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { Incident } from '../api/types';

const { Option } = Select;
const { Text } = Typography;

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

  const columns: ColumnsType<Incident> = [
    { title: 'Time', dataIndex: 'timestamp', key: 'timestamp', render: (ts) => new Date(ts).toLocaleString() },
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
        <a onClick={() => {
          setSelectedIncident(record);
          setDrawerVisible(true);
        }}>Details</a>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Space wrap>
            <Space>
              <span>Container:</span>
              <Select
                style={{ width: 250 }}
                value={selectedContainerId}
                onChange={setSelectedContainerId}
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
              columns={columns} 
              rowKey={(record) => `${record.container_id}-${record.timestamp}-${record.event_type}`}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1200 }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedIncident(record);
                  setDrawerVisible(true);
                },
                style: { cursor: 'pointer' }
              })}
            />
          )}
        </Card>

        <Drawer
          title="Incident Details"
          placement="right"
          width={600}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
        >
          {selectedIncident && (
            <Descriptions column={1} bordered>
              <Descriptions.Item label="Container">{selectedIncident.container_id}</Descriptions.Item>
              <Descriptions.Item label="Time">{new Date(selectedIncident.timestamp).toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="Threat Score">
                <Tag color={selectedIncident.threat_score > 80 ? 'red' : (selectedIncident.threat_score > 50 ? 'orange' : 'green')}>
                  {selectedIncident.threat_score.toFixed(2)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Attribute">{selectedIncident.attribute_name}</Descriptions.Item>
              <Descriptions.Item label="Value">{selectedIncident.attribute_value}</Descriptions.Item>
              <Descriptions.Item label="Event Type">{selectedIncident.event_type}</Descriptions.Item>
              <Descriptions.Item label="Process">{selectedIncident.process_name}</Descriptions.Item>
              <Descriptions.Item label="AI Analysis">
                <Text type={selectedIncident.analysis ? undefined : "secondary"} italic={!selectedIncident.analysis}>
                  {selectedIncident.analysis || "Analysis pending..."}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Details">
                <Text code>{selectedIncident.details}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Alert Content">
                <Text code>{selectedIncident.alert_content}</Text>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Drawer>
      </Space>
    </div>
  );
};

export default Incidents;
