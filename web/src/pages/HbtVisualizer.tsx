import React, { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Empty, Spin, Alert, Select, Space } from 'antd';
import { api } from '../api/client';
import Chart from '../components/Chart';
import type { ContainerSummary } from '../api/types';
import * as echarts from 'echarts';

/**
 * 把行为树节点的 children 从对象形态规整成数组。
 *
 * 后端序列化时 children 是 `{name: node}` 的字典（保持插入顺序），而 echarts 的
 * tree 系列只认数组，所以在渲染前统一转换一次。
 */
function normalizeChildren(node: any): any {
  if (!node || typeof node !== 'object') return node;

  const childrenObj = node.children;
  let childrenArr: any[] = [];
  if (childrenObj && !Array.isArray(childrenObj)) {
    childrenArr = Object.keys(childrenObj).map((key) => normalizeChildren(childrenObj[key]));
  } else if (Array.isArray(childrenObj)) {
    childrenArr = childrenObj.map((child: any) => normalizeChildren(child));
  }
  return { ...node, children: childrenArr };
}

/** tooltip 内容：节点名、类型与命中次数。模板里的缩进会原样进 HTML，不要重新排版。 */
function tooltipFormatter(params: any): string {
  const data = params.data;
  return `
                <div style="text-align: left;">
                    <b>${data.name}</b> (${data.type})<br/>
                    Events: ${data.events_count || 0}<br/>
                </div>
            `;
}

/** 节点标签：命中次数大于 0 时用 rich 样式附带计数，否则只显示名字 */
function labelFormatter(params: any): string {
  return params.data.events_count > 0
    ? `{name|${params.name}} {count|(${params.data.events_count})}`
    : params.name;
}

/** 标签富文本样式：名字常规色，计数用告警红 */
const LABEL_RICH = {
  name: {
    color: '#333',
    fontSize: 14
  },
  count: {
    color: '#ff4d4f',
    fontSize: 12,
    padding: [0, 0, 0, 4]
  }
};

/** 叶子标签靠右排布，避免与父节点标签重叠（字面量类型要保留，echarts 按联合类型校验） */
const LEAF_LABEL = {
  position: 'right' as const,
  verticalAlign: 'middle' as const,
  align: 'left' as const
};

/** 容器选择器：从活跃容器里挑一个看画像 */const ContainerPicker: React.FC<{
  containers: ContainerSummary[];
  value: string | null;
  onChange: (id: string) => void;
}> = ({ containers, value, onChange }) => (
  <Card>
    <Space>
      <span>Select Container:</span>
      <Select
        style={{ width: 300 }}
        value={value}
        onChange={onChange}
        options={containers.map(c => ({ label: c.name, value: c.id }))}
      />
    </Space>
  </Card>
);

const HbtVisualizer: React.FC = () => {
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(null);

  // 首次拿到容器列表后自动选中第一个，省掉一次手动选择
  React.useEffect(() => {
    if (containers && containers.length > 0 && !selectedContainerId) {
      setSelectedContainerId(containers[0].id);
    }
  }, [containers, selectedContainerId]);

  const {
    data: hbtData,
    isLoading,
    error
  } = useQuery({
    queryKey: ['hbt', selectedContainerId],
    queryFn: () => selectedContainerId ? api.getHbtSnapshot(selectedContainerId) : Promise.reject('No container selected'),
    enabled: !!selectedContainerId,
    retry: false
  });

  const normalizeTree = useCallback((node: any) => normalizeChildren(node), []);

  const chartOption: echarts.EChartsOption = useMemo(() => {
    if (!hbtData || !hbtData.hbt_structure) return {};

    const data = normalizeTree(hbtData.hbt_structure);
    return {
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        formatter: tooltipFormatter
      },
      series: [
        {
          type: 'tree',
          data: [data],
          top: '1%',
          left: '7%',
          bottom: '1%',
          right: '20%',
          symbolSize: 12,
          label: {
            position: 'left',
            verticalAlign: 'middle',
            align: 'right',
            fontSize: 14,
            formatter: labelFormatter,
            rich: LABEL_RICH
          },
          leaves: {
            label: LEAF_LABEL
          },
          emphasis: {
            focus: 'descendant'
          },
          expandAndCollapse: true,
          animationDuration: 550,
          animationDurationUpdate: 750,
          initialTreeDepth: 2
        }
      ]
    };
  }, [hbtData]);

  if (!containers || containers.length === 0) {
    return (
        <Card title="Container Behavior Tree (HBT)">
            <Empty description="No active containers found to visualize" />
        </Card>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <ContainerPicker
          containers={containers}
          value={selectedContainerId}
          onChange={setSelectedContainerId}
        />

        <Card title="Hierarchical Behavior Tree" bordered={false} bodyStyle={{ height: '800px' }}>
            {isLoading && <div style={{ textAlign: 'center', marginTop: 100 }}><Spin size="large" /></div>}

            {error && (
                <Alert 
                    message="Failed to load HBT Snapshot" 
                    description="The snapshot file might not exist yet for this container. Wait for Hanabi worker to generate it." 
                    type="warning" 
                    showIcon 
                />
            )}

            {!isLoading && !error && hbtData && (
                <Chart options={chartOption} height="100%" />
            )}
        </Card>
      </Space>
    </div>
  );
};

export default HbtVisualizer;
