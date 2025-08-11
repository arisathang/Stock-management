// src/App.js (with History)

import React, { useState, useEffect, useCallback } from 'react';
import LivePage from './pages/live';
import ReportPage from './pages/report';
import Header from './components/Header';

const API_URL = process.env.REACT_APP_API_URL || '/api';

// Helper to get today's date in YYYY-MM-DD format
const getTodayDateString = () => new Date().toISOString().split('T')[0];

export default function App() {
  const [currentPage, setCurrentPage] = useState('live');
  const [selectedDate, setSelectedDate] = useState(getTodayDateString());
  const [stockItems, setStockItems] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [invoice, setInvoice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);

  const fetchStockStatus = useCallback(async (date) => {
    try {
      setIsLoading(true);
      setError(null);
      // Pass the selected date as a query parameter
      const response = await fetch(`${API_URL}/stock-status?date=${date}`);
      if (!response.ok) throw new Error(`Network error (${response.status})`);
      const data = await response.json();
      setStockItems(data.stockItems);
      setAlerts(data.alerts);
    } catch (error) {
      setError(`Failed to fetch stock status for ${date}: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStockStatus(selectedDate);
  }, [selectedDate, fetchStockStatus]);

  const handleStockChange = useCallback(async (id, value) => {
    if (isNaN(value)) return;

    const originalStock = [...stockItems];
    setStockItems(prevItems =>
      prevItems.map(item => (item.id === id ? { ...item, remaining_stock: value } : item))
    );

    try {
      await fetch(`${API_URL}/update-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, remainingStock: value, date: selectedDate }),
      });
      // Re-fetch to confirm and get updated alerts
      fetchStockStatus(selectedDate);
    } catch (error) {
      setError(`Failed to update stock. Reverting changes.`);
      setStockItems(originalStock);
    }
  }, [stockItems, selectedDate, fetchStockStatus]);

  const handleGenerateInvoice = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = { stockItems };
      const response = await fetch(`${API_URL}/generate-invoice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Invoice generation failed.');
      }
      const result = await response.json();
      setInvoice(result.invoice);
    } catch (error) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  }, [stockItems]);

  const handleNavigate = (page) => {
    setCurrentPage(page);
  };

  const PageToRender = () => {
    if (currentPage === 'live') {
      return (
        <LivePage
          stockItems={stockItems}
          onStockChange={handleStockChange}
          selectedDate={selectedDate}
          setSelectedDate={setSelectedDate}
          isToday={selectedDate === getTodayDateString()}
        />
      );
    }
    if (currentPage === 'report') {
      return <ReportPage invoice={invoice} onGenerate={handleGenerateInvoice} isLoading={isLoading} />;
    }
    return null;
  };

  if (error) {
    return <div className="flex justify-center items-center min-h-screen text-red-500 font-bold text-xl p-8">{error}</div>;
  }

  return (
    <div>
      <Header
        currentPage={currentPage}
        onNavigate={handleNavigate}
        alertCount={alerts.length}
        onToggleNotifications={() => setShowNotifications(!showNotifications)}
      />
      {showNotifications && (
         <div className="absolute top-16 right-4 mt-2 w-80 bg-white rounded-lg shadow-xl p-4 z-50">
            <h3 className="font-bold mb-2">Notifications</h3>
            {alerts.length > 0 ? (
            <ul className="space-y-2">{alerts.map((alert, index) => <li key={index} className="text-sm text-gray-700"><span className={alert.type === 'low' ? 'text-red-600' : 'text-blue-600'}>● </span>{alert.message}</li>)}</ul>
            ) : (
            <p className="text-sm text-gray-500">No new alerts.</p>
            )}
        </div>
      )}
      {isLoading && stockItems.length === 0 ? <div className="flex justify-center items-center p-10">Loading initial data...</div> : <PageToRender />}
    </div>
  );
}
