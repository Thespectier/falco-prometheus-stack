import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Empty, Spin, Alert, Select, Space } from 'antd';
import { api } from '../api/client';
import Chart from '../components/Chart';
import * as echarts from 'echarts';

const HbtVisualizer: React.FC = () => {
  // In a real app, we'd select the container ID. For now, we fetch the list and pick the first one or allow selection.
  // Let's fetch active containers first.
  const { data: containers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => api.listContainers(),
  });

  const [selectedContainerId, setSelectedContainerId] = React.useState<string | null>(null);

  // Auto-select first container if available and none selected
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

  const chartOption: echarts.EChartsOption = useMemo(() => {
    if (!hbtData || !hbtData.hbt_structure) return {};

    return {
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        formatter: (params: any) => {
            const data = params.data;
            return `
                <div style="text-align: left;">
                    <b>${data.name}</b> (${data.type})<br/>
                    Events: ${data.events_count || 0}<br/>
                </div>
            `;
        }
      },
      series: [
        {
          type: 'tree',
          data: [hbtData.hbt_structure],
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
            formatter: (params: any) => {
                // Show event count in label if > 0
                return params.data.events_count > 0 
                    ? `{name|${params.name}} {count|(${params.data.events_count})}`
                    : params.name;
            },
            rich: {
                name: {
                    color: '#333',
                    fontSize: 14
                },
                count: {
                    color: '#ff4d4f',
                    fontSize: 12,
                    padding: [0, 0, 0, 4]
                }
            }
          },
          leaves: {
            label: {
              position: 'right',
              verticalAlign: 'middle',
              align: 'left'
            }
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
        <Card>
            <Space>
                <span>Select Container:</span>
                <Select
                    style={{ width: 300 }}
                    value={selectedContainerId}
                    onChange={setSelectedContainerId}
                    options={containers.map(c => ({ label: c.name, value: c.id }))}
                />
            </Space>
        </Card>

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
