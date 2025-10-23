import React, { useEffect, useState } from 'react';
import { dashboardSummary } from '../api';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

export default function Dashboard() {
  const [data, setData] = useState({
    total_products: 0,
    low_stock_count: 0,
    open_pos: 0,
    recent_movements: []
  });

  useEffect(() => {
    dashboardSummary()
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return <div>Loading...</div>;

  const pieData = [
    { name: 'Low stock', value: data.low_stock_count },
    { name: 'OK', value: Math.max(0, data.total_products - data.low_stock_count) }
  ];

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 bg-white p-4 rounded shadow">
        <h3 className="text-lg font-semibold">Summary</h3>
        <div className="flex gap-4 mt-4">
          <div className="p-4 bg-gray-50 rounded">
            <div className="text-sm">Products</div>
            <div className="text-2xl font-bold">{data.total_products}</div>
          </div>
          <div className="p-4 bg-gray-50 rounded">
            <div className="text-sm">Low stock</div>
            <div className="text-2xl font-bold">{data.low_stock_count}</div>
          </div>
          <div className="p-4 bg-gray-50 rounded">
            <div className="text-sm">Open POs</div>
            <div className="text-2xl font-bold">{data.open_pos}</div>
          </div>
        </div>

        <h4 className="mt-6 font-semibold">Recent movements</h4>
        <ul className="mt-2 space-y-2">
          {(data.recent_movements || []).map((m) => (
            <li key={m.id} className="text-sm">
              {m.created_at} — Prod {m.product_id} — {m.type} {m.quantity}
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h3 className="text-lg font-semibold">Stock distribution</h3>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                outerRadius={80}
                fill="#8884d8"
              >
                {pieData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={index === 0 ? '#ef4444' : '#10b981'}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
