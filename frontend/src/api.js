import axios from 'axios';
const API_BASE = 'https://calm-backend-doe9.onrender.com';

export function setToken(token){ localStorage.setItem('token', token); axios.defaults.headers.common['Authorization'] = `Bearer ${token}`; }
export function clearToken(){ localStorage.removeItem('token'); delete axios.defaults.headers.common['Authorization']; }

export async function login(username, password){ const params = new URLSearchParams(); params.append('username', username); params.append('password', password); const res = await axios.post(`${API_BASE}/token`, params); return res.data; }
export async function fetchProducts(q=''){ const res = await axios.get(`${API_BASE}/products`, { params: { q } }); return res.data; }
export async function fetchSuppliers(){ const res = await axios.get(`${API_BASE}/suppliers`); return res.data; }
export async function fetchWarehouses(){ const res = await axios.get(`${API_BASE}/warehouses`); return res.data; }
export async function createPurchase(payload){ const res = await axios.post(`${API_BASE}/purchase_orders`, payload); return res.data; }
export async function fetchPurchaseOrders(){ const res = await axios.get(`${API_BASE}/purchase_orders`); return res.data; }
export async function receivePurchase(po_id, payload){ const res = await axios.post(`${API_BASE}/purchase_orders/${po_id}/receive`, payload); return res.data; }
export async function fetchMovements(){ const res = await axios.get(`${API_BASE}/stock/movements`); return res.data; }
export async function importProducts(file){ const fd = new FormData(); fd.append('file', file); const res = await axios.post(`${API_BASE}/import/products`, fd); return res.data; }
export async function exportProducts(){ const res = await axios.get(`${API_BASE}/export/products`, { responseType: 'blob' }); return res; }
export async function dashboardSummary(){ const res = await axios.get(`${API_BASE}/dashboard/summary`); return res.data; }
export async function seed(){ const res = await axios.post(`${API_BASE}/seed`); return res.data; }
