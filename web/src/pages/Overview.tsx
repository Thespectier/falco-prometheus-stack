import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, Table } from 'antd';
import { FundProjectionScreenOutlined, ContainerOutlined, AppstoreOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import Chart from '../components/Chart';
import type { ColumnsType } from 'antd/es/table';
import { ContainerSummary } from '../api/types';
import * as echarts from 'echarts';

const Overview: React.FC = () => {
  // Fetch Overview Metrics
  const { 
    data: overviewData, 
    isLoading: isOverviewLoading, 
    error: overviewError 
  } = useQuery({
    queryKey: ['overview'],
    queryFn: () => api.getOverview(),
    refetchInterval: 5000 // Refresh every 5s
  });

  // Fetch Active Containers
  const { 
    data: containersData, 
    isLoading: isContainersLoading 
  } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
    refetchInterval: 10000
  });

  if (isOverviewLoading || isContainersLoading) {
    return <div style={{ textAlign: 'center', padding: '50px' }}><Spin size="large" /></div>;
  }

  if (overviewError) {
    return <Alert message="Error loading overview data" type="error" showIcon />;
  }

  // Prepare Chart Options
  const priorityChartOption: echarts.EChartsOption = {
    title: { text: 'Events by Priority', left: 'center' },
    tooltip: { trigger: 'item' },
    legend: { bottom: '0%' },
    series: [
      {
        name: 'Priority',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: 20, fontWeight: 'bold' } },
        data: overviewData?.priority_distribution.map(d => ({ value: d.value, name: d.priority })) || []
      }
    ]
  };

  const categoryChartOption: echarts.EChartsOption = {
    title: { text: 'Events by Category', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: overviewData?.category_distribution.map(d => d.category) || [] },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Count',
        type: 'bar',
        data: overviewData?.category_distribution.map(d => d.value) || [],
        itemStyle: { color: '#5470c6' }
      }
    ]
  };

  const containerColumns: ColumnsType<ContainerSummary> = [
    { title: 'Container Name', dataIndex: 'name', key: 'name' },
    { 
      title: 'Event Rate (5m)', 
      dataIndex: 'event_rate', 
      key: 'event_rate',
      render: (val) => val.toFixed(2),
      sorter: (a, b) => a.event_rate - b.event_rate,
      defaultSortOrder: 'descend'
    },
    { 
      title: 'Last Seen', 
      dataIndex: 'last_seen', 
      key: 'last_seen',
      render: (ts) => new Date(ts * 1000).toLocaleString() 
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ marginBottom: '24px' }}>System Overview</h2>
      
      {/* Top Metrics Cards */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={8}>
          <Card bordered={false}>
            <Statistic
              title="Total Event Rate (5m)"
              value={overviewData?.total_events_rate}
              precision={2}
              prefix={<FundProjectionScreenOutlined />}
              suffix="ev/s"
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false}>
            <Statistic
              title="Active Containers"
              value={overviewData?.active_containers_count}
              prefix={<ContainerOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false}>
            <Statistic
              title="Monitored Rules"
              value={overviewData?.category_distribution.length} 
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts Row */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={12}>
          <Card title="Distribution by Priority" bordered={false}>
            <Chart options={priorityChartOption} height="300px" />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Distribution by Category" bordered={false}>
            <Chart options={categoryChartOption} height="300px" />
          </Card>
        </Col>
      </Row>

      {/* Top Containers Table */}
      <Card title="Active Containers Activity" bordered={false}>
        <Table 
          dataSource={containersData} 
          columns={containerColumns} 
          rowKey="id"
          pagination={{ pageSize: 5 }} 
        />
      </Card>
    </div>
  );
};

export default Overview;
