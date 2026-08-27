"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend
} from "recharts";
import { format, parseISO } from "date-fns";

export const CHART_COLORS = {
  success: "#10b981", // emerald-500
  failure: "#ef4444", // red-500
  retry: "#f59e0b", // amber-500
  info: "#3b82f6", // blue-500
  neutral: "#64748b", // slate-500
};

interface TooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  valueFormatter?: (val: number) => string;
}

const CustomTooltip = ({ active, payload, label, valueFormatter }: TooltipProps) => {
  if (active && payload && payload.length) {
    const formattedDate = label ? format(new Date(label), "MMM d, HH:mm") : "";
    return (
      <div className="bg-popover text-popover-foreground border shadow-sm p-3 rounded-lg text-sm">
        <p className="font-semibold mb-2">{formattedDate}</p>
        <div className="space-y-1">
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <div className="flex items-center">
                <div
                  className="w-2 h-2 rounded-full mr-2"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-muted-foreground">{entry.name}</span>
              </div>
              <span className="font-medium">
                {valueFormatter ? valueFormatter(entry.value) : entry.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

interface TrendLineChartProps {
  data: any[];
  dataKey: string;
  name?: string;
  color?: string;
  valueFormatter?: (val: number) => string;
  xAxisFormatter?: (val: string) => string;
  threshold?: { value: number; label: string; color?: string };
}

export function TrendLineChart({
  data,
  dataKey,
  name = "Value",
  color = CHART_COLORS.info,
  valueFormatter,
  xAxisFormatter,
  threshold,
}: TrendLineChartProps) {
  // If no data, show empty state (handled by parent typically, but good to be safe)
  if (!data || data.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center text-muted-foreground text-sm">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" opacity={0.1} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={xAxisFormatter || ((tick) => format(new Date(tick), "HH:mm"))}
          stroke="currentColor"
          fontSize={12}
          opacity={0.5}
          tickLine={false}
          axisLine={false}
          minTickGap={30}
        />
        <YAxis
          tickFormatter={valueFormatter}
          stroke="currentColor"
          fontSize={12}
          opacity={0.5}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip valueFormatter={valueFormatter} />} />
        
        {threshold && (
          <ReferenceLine
            y={threshold.value}
            stroke={threshold.color || CHART_COLORS.failure}
            strokeDasharray="3 3"
            label={{
              position: "insideTopLeft",
              value: `${threshold.label}: ${valueFormatter ? valueFormatter(threshold.value) : threshold.value}`,
              fill: threshold.color || CHART_COLORS.failure,
              fontSize: 12,
            }}
          />
        )}
        
        <Line
          type="linear"
          dataKey={dataKey}
          name={name}
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
          connectNulls={true}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export interface SeriesConfig {
  dataKey: string;
  name: string;
  color: string;
  strokeDasharray?: string;
}

interface MultiSeriesChartProps {
  data: any[];
  series: SeriesConfig[];
  valueFormatter?: (val: number) => string;
  xAxisFormatter?: (val: string) => string;
  type?: "line" | "area";
}

export function MultiSeriesChart({
  data,
  series,
  valueFormatter,
  xAxisFormatter,
  type = "line",
}: MultiSeriesChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center text-muted-foreground text-sm">
        No data available
      </div>
    );
  }

  const ChartComponent = type === "area" ? AreaChart : LineChart;

  return (
    <ResponsiveContainer width="100%" height="100%">
      {/* @ts-ignore Recharts typing is a bit loose with dynamic component rendering */}
      <ChartComponent data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" opacity={0.1} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={xAxisFormatter || ((tick) => format(new Date(tick), "HH:mm"))}
          stroke="currentColor"
          fontSize={12}
          opacity={0.5}
          tickLine={false}
          axisLine={false}
          minTickGap={30}
        />
        <YAxis
          tickFormatter={valueFormatter}
          stroke="currentColor"
          fontSize={12}
          opacity={0.5}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip valueFormatter={valueFormatter} />} />
        <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
        
        {series.map((s, idx) => {
          if (type === "area") {
            return (
              <Area
                key={s.dataKey}
                type="linear"
                dataKey={s.dataKey}
                name={s.name}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.1}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                connectNulls={true}
                strokeDasharray={s.strokeDasharray}
              />
            );
          }
          return (
            <Line
              key={s.dataKey}
              type="linear"
              dataKey={s.dataKey}
              name={s.name}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              connectNulls={true}
              strokeDasharray={s.strokeDasharray}
            />
          );
        })}
      </ChartComponent>
    </ResponsiveContainer>
  );
}
