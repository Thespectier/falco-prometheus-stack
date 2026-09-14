import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag, Select, Space, Empty, Typography, Drawer, Descriptions } from 'antd';
import { FileTextOutlined, ThunderboltOutlined, DisconnectOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { ColumnsType } from 'antd/es/table';
import { ContainerSummary, LogEvent } from '../api/types';

const { Option } = Select;
const { Text } = Typography;

/** 事件优先级 → 标签配色；未知优先级落到 default */
const PRIORITY_COLORS: Record<string, string> = {
  'Critical': 'red',
  'Error': 'volcano',
  'Warning': 'orange',
  'Notice': 'gold',
  'Info': 'blue',
  'Debug': 'default'
};

/** 前端只保留最近这么多条实时日志，避免长时间开着页面把内存吃满 */
const MAX_BUFFERED_LOGS = 100;

/** 未拿到配置时的兜底后端地址 */
const FALLBACK_API_BASE = 'http://localhost:8000';

/**
 * 推导日志流的 WebSocket 地址。
 *
 * 后端把 WebSocket 挂在 `/api/logs` 下（见 `api/app/routers/logs.py` 与 `main.py` 的
 * 路由前缀），而 `api.baseURL` 已经是带前缀的 `/api`，所以这里只补 `/logs/ws/<id>`：
 * 沿用相对地址时用当前页面的 host，绝对地址时把 http(s) 换成 ws(s)。
 */
function buildLogStreamUrl(apiBase: string, protocol: string, host: string, containerId: string): string {
  const baseUrl = apiBase || FALLBACK_API_BASE;
  const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
  const wsBase = baseUrl.startsWith('http')
    ? baseUrl.replace(/^http/, 'ws')
    : `${wsProtocol}//${host}${baseUrl}`;
  return `${wsBase}/logs/ws/${containerId}`;
}

/** 优先级标签：抽屉与表格共用 */
const PriorityTag: React.FC<{ priority?: string }> = ({ priority }) => (
  <Tag color={PRIORITY_COLORS[priority || ''] || 'default'}>
    {priority ? priority.toUpperCase() : 'UNKNOWN'}
  </Tag>
);

/** 表格列定义；"Details" 列要打开抽屉，由调用方注入回调 */
function buildColumns(openDetails: (record: LogEvent) => void): ColumnsType<LogEvent> {
  return [
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
      render: (priority) => <PriorityTag priority={priority} />,
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
        <a onClick={() => openDetails(record)}>Details</a>
      ),
    },
  ];
}

/** 容器选择器 + 实时连接状态 */
const LogStreamToolbar: React.FC<{
  containers: ContainerSummary[];
  containerId: string | null;
  onContainerChange: (id: string) => void;
  connected: boolean;
}> = ({ containers, containerId, onContainerChange, connected }) => (
  <Card>
    <Space>
      <span>Container:</span>
      <Select
        style={{ width: 300 }}
        value={containerId}
        onChange={onContainerChange}
        placeholder="Select a container"
      >
        {containers.map(c => (
          <Option key={c.id} value={c.id}>{c.name}</Option>
        ))}
      </Select>
      {connected ? (
          <Tag icon={<ThunderboltOutlined />} color="success">Live Streaming</Tag>
      ) : (
          <Tag icon={<DisconnectOutlined />} color="error">Disconnected</Tag>
      )}
    </Space>
  </Card>
);

/** 日志详情抽屉 */
const LogDetailsDrawer: React.FC<{
  log: LogEvent | null;
  visible: boolean;
  onClose: () => void;
}> = ({ log, visible, onClose }) => (
  <Drawer
    title="Log Details"
    placement="right"
    width={600}
    onClose={onClose}
    open={visible}
  >
    {log && (
      <Descriptions column={1} bordered>
        <Descriptions.Item label="Time">
          {new Date(log.timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
        </Descriptions.Item>
        <Descriptions.Item label="Priority">
          <PriorityTag priority={log.priority} />
        </Descriptions.Item>
        <Descriptions.Item label="Rule">{log.rule}</Descriptions.Item>
        <Descriptions.Item label="Source">{log.source}</Descriptions.Item>
        <Descriptions.Item label="Tags">
          {log.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}
        </Descriptions.Item>
        <Descriptions.Item label="Output">
          <Text code>{log.output}</Text>
        </Descriptions.Item>
      </Descriptions>
    )}
  </Drawer>
);

const Logs: React.FC = () => {
  // 容器列表：决定能选哪些流
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEvent | null>(null);

  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // 首次拿到容器列表后自动选第一个
  useEffect(() => {
    if (containers && containers.length > 0 && !selectedContainerId) {
      setSelectedContainerId(containers[0].id);
    }
  }, [containers, selectedContainerId]);

  // 订阅选中容器的日志流；切换容器或卸载时断开
  useEffect(() => {
    if (!selectedContainerId) return;

    if (wsRef.current) {
      wsRef.current.close();
    }

    // 切换容器时清空缓冲：不同容器的日志混在一起没法看
    setLogs([]);

    const wsUrl = buildLogStreamUrl(
      api.baseURL,
      window.location.protocol,
      window.location.host,
      selectedContainerId
    );

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const logData = JSON.parse(event.data);
        // 后端下发的 timestamp 是 Unix 秒，tags 是 JSON 字符串
        const newLog: LogEvent = {
          timestamp: new Date(logData.timestamp * 1000).toISOString(),
          rule: logData.rule,
          priority: logData.priority,
          source: logData.source,
          output: logData.output,
          tags: JSON.parse(logData.tags || '[]')
        };

        setLogs(prev => {
          const updated = [newLog, ...prev];
          if (updated.length > MAX_BUFFERED_LOGS) {
            return updated.slice(0, MAX_BUFFERED_LOGS);
          }
          return updated;
        });
      } catch (err) {
        console.error('Error parsing log message:', err);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket Disconnected');
      setIsConnected(false);
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [selectedContainerId]);

  const openDetails = (record: LogEvent) => {
    setSelectedLog(record);
    setDrawerVisible(true);
  };

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

        <LogStreamToolbar
          containers={containers}
          containerId={selectedContainerId}
          onContainerChange={setSelectedContainerId}
          connected={isConnected}
        />

        <Card 
          title={
            <Space>
              <FileTextOutlined />
              <span>Security Events Log (Real-time Buffer: {logs.length}/{MAX_BUFFERED_LOGS})</span>
            </Space>
          }
        >
          <Table 
            dataSource={logs} 
            columns={buildColumns(openDetails)} 
            rowKey={(record, index) => `${record.timestamp}-${index}`}
            pagination={{ pageSize: 20 }}
            scroll={{ x: 1000 }}
            locale={{ emptyText: isConnected ? 'Waiting for events...' : 'No logs (disconnected)' }}
            onRow={(record) => ({
              onClick: () => openDetails(record),
              style: { cursor: 'pointer' }
            })}
          />
        </Card>

        <LogDetailsDrawer
          log={selectedLog}
          visible={drawerVisible}
          onClose={() => setDrawerVisible(false)}
        />
      </Space>
    </div>
  );
};

export default Logs;
