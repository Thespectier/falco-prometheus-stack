import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface ChartProps {
  options: echarts.EChartsOption;
  height?: string | number;
}

const Chart: React.FC<ChartProps> = ({ options, height = '300px' }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts>();

  useEffect(() => {
    if (chartRef.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }

    const resizeObserver = new ResizeObserver(() => {
      chartInstance.current?.resize();
    });

    if (chartRef.current) {
      resizeObserver.observe(chartRef.current);
    }

    return () => {
      chartInstance.current?.dispose();
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    chartInstance.current?.setOption(options);
  }, [options]);

  return <div ref={chartRef} style={{ height, width: '100%' }} />;
};

export default Chart;
