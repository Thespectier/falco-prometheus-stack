import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

const DEFAULT_HEIGHT = '300px';

interface ChartProps {
  options: echarts.EChartsOption;
  height?: string | number;
}

/**
 * 管理 echarts 实例的生命周期。
 *
 * 只在挂载时初始化一次（后续配置变化走 setOption，避免整图重建导致动画与缩放丢失）；
 * 容器尺寸变化由 ResizeObserver 触发 resize，卸载时销毁实例并断开观察。
 */
function useECharts(options: echarts.EChartsOption) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts>();

  useEffect(() => {
    if (containerRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }

    const resizeObserver = new ResizeObserver(() => {
      chartRef.current?.resize();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      chartRef.current?.dispose();
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(options);
  }, [options]);

  return containerRef;
}

/** 通用图表容器：只负责挂载点与生命周期，具体图形由 options 决定 */
const Chart: React.FC<ChartProps> = ({ options, height = DEFAULT_HEIGHT }) => {
  const containerRef = useECharts(options);
  return <div ref={containerRef} style={{ height, width: '100%' }} />;
};

export default Chart;
