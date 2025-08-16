import React, { useState, useEffect, useCallback } from 'react';
import LivePage from './pages/live';
import ReportPage from './pages/report';
import Header from './components/Header';

const API_URL = process.env.REACT_APP_API_URL || '/api';

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
  const [vendors, setVendors] = useState([]);
  const [movementLog, setMovementLog] = useState([]);
  const [invoiceLogs, setInvoiceLogs] = useState({});

  const fetchStockStatus = useCallback(async (date) => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await fetch(`${API_URL}/stock-status?date=${date}`);
      if (!response.ok) throw new Error(`Network error (${response.status})`);
      const data = await response.json();
      setStockItems(data.stockItems);
      setAlerts(data.alerts);
    } catch (err) {
      setError(`Failed to fetch stock status for ${date}: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const fetchMovementLog = useCallback(async () => {
      try {
          const response = await fetch(`${API_URL}/movement-log`);
          if (!response.ok) throw new Error('Failed to fetch movement log');
          const data = await response.json();
          setMovementLog(data);
      } catch (err) {
          setError(err.message);
      }
  }, []);

  useEffect(() => {
    const fetchVendors = async () => {
      try {
        const response = await fetch(`${API_URL}/vendors`);
        if (!response.ok) throw new Error('Failed to fetch vendors');
        const data = await response.json();
        setVendors(data);
      } catch (err) {
        setError(err.message);
      }
    };
    fetchVendors();
    fetchStockStatus(selectedDate);
    fetchMovementLog();
  }, [selectedDate, fetchStockStatus, fetchMovementLog]);

  const handleRecordMovement = useCallback(async (movementData) => {
    try {
      await fetch(`${API_URL}/record-movement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(movementData),
      });
      fetchStockStatus(selectedDate);
      fetchMovementLog();
    } catch (err) {
      setError(`Failed to record movement: ${err.message}`);
    }
  }, [selectedDate, fetchStockStatus, fetchMovementLog]);

  const handleGenerateInvoice = useCallback(async (vendorFilter) => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = { stockItems, vendorFilter };
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
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [stockItems]);

  const handleSaveInvoice = useCallback(async (invoiceData) => {
      try {
          const response = await fetch(`${API_URL}/save-invoice`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(invoiceData)
          });
          if (!response.ok) throw new Error('Failed to save invoice');
          const data = await response.json();
          alert('Invoice saved successfully!');
          return data.invoiceId;
      } catch (err) {
          setError(err.message);
          return null;
      }
  }, []);
  
  const handleStatusUpdate = useCallback(async (statusUpdateData) => {
      try {
          await fetch(`${API_URL}/update-invoice-status`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(statusUpdateData)
          });
           // The fix is here: After approving, refresh the stock status and movement log
          if (statusUpdateData.newStatus === 'Approved') {
              fetchStockStatus(selectedDate);
              fetchMovementLog();
          }
      } catch (err) {
          setError(err.message);
      }
  }, [selectedDate, fetchStockStatus, fetchMovementLog]);

  const handleFetchLogs = useCallback(async (invoiceId) => {
      try {
          const response = await fetch(`${API_URL}/invoice-logs/${invoiceId}`);
          if (!response.ok) throw new Error('Failed to fetch logs');
          const data = await response.json();
          setInvoiceLogs(prev => ({ ...prev, [invoiceId]: data }));
      } catch (err) {
          setError(err.message);
      }
  }, []);

  const handleNavigate = (page) => {
    setCurrentPage(page);
  };

  const PageToRender = () => {
    if (currentPage === 'live') {
      return (
        <LivePage
          stockItems={stockItems}
          onRecordMovement={handleRecordMovement}
          selectedDate={selectedDate}
          setSelectedDate={setSelectedDate}
          isToday={selectedDate === getTodayDateString()}
        />
      );
    }
    if (currentPage === 'report') {
      return (
        <ReportPage
          invoice={invoice}
          onGenerate={handleGenerateInvoice}
          isLoading={isLoading}
          vendors={vendors}
          onSave={handleSaveInvoice}
          onStatusUpdate={handleStatusUpdate}
          movementLog={movementLog}
          onFetchLogs={handleFetchLogs}
          invoiceLogs={invoiceLogs}
        />
      );
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
