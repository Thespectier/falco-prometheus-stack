import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, Table } from 'antd';
import { FundProjectionScreenOutlined, ContainerOutlined, AppstoreOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import Chart from '../components/Chart';
import type { ColumnsType } from 'antd/es/table';
import { ContainerSummary, FunnelStats, OverviewMetrics } from '../api/types';
import * as echarts from 'echarts';

/** 顶部指标卡：标题与单位固定，数值来自总览接口 */
function buildMetricCards(overviewData?: OverviewMetrics) {
  return [
    {
      title: 'Total Event Rate (5m)',
      value: overviewData?.total_events_rate,
      precision: 2,
      prefix: <FundProjectionScreenOutlined />,
      suffix: 'ev/s',
    },
    {
      title: 'Active Containers',
      value: overviewData?.active_containers_count,
      prefix: <ContainerOutlined />,
    },
    {
      title: 'Monitored Rules',
      value: overviewData?.category_distribution.length,
      prefix: <AppstoreOutlined />,
    },
  ];
}

/** 漏斗 tooltip 展示真实数量（图形高度是示意比例，不表示数值） */
function funnelTooltipFormatter(params: any): string {
  return `${params.name}: <b>${params.data.realValue}</b>`;
}

/** 漏斗内标签：名字与真实数量分两行 */
function funnelLabelFormatter(params: any): string {
  return `${params.name}\n${params.data.realValue}`;
}

/**
 * 漏斗图配置。
 *
 * `value` 是画图用的示意比例（100/60/20），真实数量放在 `realValue` 里供 tooltip 与
 * 标签显示——漏斗的视觉尺寸与数量级无关，否则三段的面积差会看不出层次。
 */
function buildFunnelChartOption(funnelStats?: FunnelStats): echarts.EChartsOption {
  return {
    title: { text: 'Security Data Funnel (Last 30m)', left: 'center' },
    tooltip: {
        trigger: 'item',
        formatter: funnelTooltipFormatter
    },
    series: [
      {
        name: 'Funnel',
        type: 'funnel',
        left: '10%',
        top: 60,
        bottom: 60,
        width: '80%',
        min: 0,
        max: 100,
        minSize: '0%',
        maxSize: '100%',
        sort: 'none',
        gap: 2,
        label: {
          show: true,
          position: 'inside',
          formatter: funnelLabelFormatter,
          color: '#fff',
          fontWeight: 'bold'
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1
        },
        data: [
          { value: 100, name: 'Total Logs', realValue: funnelStats?.logs || 0, itemStyle: { color: '#5470c6' } },
          { value: 60, name: 'Alerts', realValue: funnelStats?.alerts || 0, itemStyle: { color: '#fac858' } },
          { value: 20, name: 'Incidents', realValue: funnelStats?.incidents || 0, itemStyle: { color: '#ee6666' } }
        ] as any[]
      }
    ]
  };
}

/** 规则类别分布柱状图 */
function buildCategoryChartOption(overviewData?: OverviewMetrics): echarts.EChartsOption {
  return {
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
}

/** 活跃容器表：速率列默认降序，时间按东八区展示 */
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
    render: (ts) => new Date(ts * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
  },
];

const Overview: React.FC = () => {
  // 总览指标：5 秒一轮，漏斗与分布图都取自这里
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    error: overviewError
  } = useQuery({
    queryKey: ['overview'],
    queryFn: () => api.getOverview(),
    refetchInterval: 5000
  });

  // 活跃容器：10 秒一轮，比指标慢——容器上下线本身没那么频繁
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

  const funnelChartOption = buildFunnelChartOption(overviewData?.funnel_stats);
  const categoryChartOption = buildCategoryChartOption(overviewData);

  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ marginBottom: '24px' }}>System Overview</h2>

      {/* 顶部指标卡 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        {buildMetricCards(overviewData).map((card) => (
          <Col span={8} key={card.title}>
            <Card bordered={false}>
              <Statistic
                title={card.title}
                value={card.value}
                precision={card.precision}
                prefix={card.prefix}
                suffix={card.suffix}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 两张图：漏斗看链路，柱状图看规则类别分布 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={12}>
          <Card title="Data Processing Pipeline" bordered={false}>
            <Chart options={funnelChartOption} height="300px" />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Distribution by Category" bordered={false}>
            <Chart options={categoryChartOption} height="300px" />
          </Card>
        </Col>
      </Row>

      {/* 活跃容器 */}
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
