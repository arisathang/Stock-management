import React, { useState, useEffect, useMemo } from 'react';
import { BarChart, FileText, RefreshCw, TrendingUp, Truck, Save, FileDown, History } from 'lucide-react';
import Select from 'react-select';
import { createRoot } from 'react-dom/client';
import InvoicePDF from '../components/InvoicePDF';

// Helper function to calculate item cost
const calculateItemCost = (quantity, item) => {
  if (!item || !item.price) return { cost: 0, savings: 0 };
  let cost = 0;
  let remainingQty = quantity;
  const nonDiscountedCost = quantity * item.price;
  
  if (item.bundles && item.bundles.length > 0) {
    const sortedBundles = [...item.bundles].sort((a, b) => b.quantity - a.quantity);
    sortedBundles.forEach(bundle => {
      const numBundles = Math.floor(remainingQty / bundle.quantity);
      if (numBundles > 0) {
        cost += numBundles * bundle.price;
        remainingQty -= numBundles * bundle.quantity;
      }
    });
  }
  
  cost += remainingQty * item.price;
  const savings = nonDiscountedCost - cost;
  return { cost, savings };
};


const ReportPage = ({ invoice, onGenerate, isLoading, vendors, onSave, onStatusUpdate, movementLog, onFetchLogs, invoiceLogs }) => {
  const [editableInvoice, setEditableInvoice] = useState(null);
  const [vendorFilter, setVendorFilter] = useState([]);
  const [statusData, setStatusData] = useState({});
  const [visibleLogVendorId, setVisibleLogVendorId] = useState(null);

  useEffect(() => {
    setEditableInvoice(invoice);
    if (invoice) {
        const initialStatus = {};
        Object.entries(invoice.vendorOrders).forEach(([vendorId, order]) => {
            initialStatus[vendorId] = { 
                status: order.status || 'Pending', 
                modifiedBy: order.modifiedBy || '', 
                invoiceId: order.invoiceId || null 
            };
        });
        setStatusData(initialStatus);
    }
  }, [invoice]);

  const handleSaveWrapper = async (vendorId, order) => {
      const newInvoiceId = await onSave({
          vendorId, 
          ...statusData[vendorId], 
          items: order.items, 
          totalCost: order.subtotal + order.shippingCost
      });
      if (newInvoiceId) {
          setStatusData(prev => ({
              ...prev,
              [vendorId]: { ...prev[vendorId], invoiceId: newInvoiceId }
          }));
      }
  };
  
  const handleViewHistory = (vendorId) => {
      const { invoiceId } = statusData[vendorId];
      if (invoiceId) {
          onFetchLogs(invoiceId);
          setVisibleLogVendorId(prev => prev === vendorId ? null : vendorId);
      }
  };

  const handleQuantityChange = (vendorId, itemId, newQuantity) => {
    const newInvoice = { ...editableInvoice };
    const order = newInvoice.vendorOrders[vendorId];
    const item = order.items.find(i => i.id === itemId);

    if (item) {
      item.quantity = newQuantity;
      const { cost } = calculateItemCost(newQuantity, item);
      item.cost = cost;
    }
    setEditableInvoice(newInvoice);
  };

  const handleStatusChange = async (vendorId, field, value) => {
      const order = editableInvoice.vendorOrders[vendorId];
      let currentInvoiceId = statusData[vendorId]?.invoiceId;
      const oldStatus = statusData[vendorId]?.status;
      const modifiedBy = field === 'modifiedBy' ? value : statusData[vendorId]?.modifiedBy;
      const newStatus = field === 'status' ? value : oldStatus;

      // If status is changed on an unsaved invoice, save it first to get an ID.
      if (field === 'status' && !currentInvoiceId) {
          const newId = await onSave({
              vendorId, status: newStatus, modifiedBy,
              items: order.items, totalCost: order.subtotal + order.shippingCost
          });
          if (newId) {
              currentInvoiceId = newId;
              // Log this initial status change
              onStatusUpdate({ invoiceId: newId, oldStatus: 'Pending', newStatus, changedBy: modifiedBy });
          }
      } else if (field === 'status' && onStatusUpdate && currentInvoiceId) {
          // If it already has an ID, just update the status
          onStatusUpdate({ invoiceId: currentInvoiceId, oldStatus, newStatus, changedBy: modifiedBy });
      }

      // Update local UI state
      setStatusData(prev => ({
          ...prev,
          [vendorId]: { ...prev[vendorId], [field]: value, invoiceId: currentInvoiceId || prev[vendorId].invoiceId }
      }));
  };

  const calculatedTotals = useMemo(() => {
    if (!editableInvoice) return null;
    let totalCost = 0, totalBundleSavings = 0, totalShippingSavings = 0;

    Object.values(editableInvoice.vendorOrders).forEach(order => {
      order.subtotal = order.items.reduce((sum, item) => sum + item.cost, 0);
      order.bundleSavings = order.items.reduce((sum, item) => sum + calculateItemCost(item.quantity, item).savings, 0);

      if (order.subtotal >= order.freeShippingThreshold) {
        order.shippingCost = 0;
        totalShippingSavings += order.originalShippingCost;
      } else {
        order.shippingCost = order.originalShippingCost;
      }
      totalCost += order.subtotal + order.shippingCost;
      totalBundleSavings += order.bundleSavings;
    });

    return { totalCost, totalBundleSavings, totalShippingSavings, totalSavings: totalBundleSavings + totalShippingSavings };
  }, [editableInvoice]);

  const vendorOptions = Array.isArray(vendors) ? vendors.map(v => ({ value: v.id, label: v.name })) : [];

  const handlePdfClick = (order, vendorId) => {
    const pdfWindow = window.open('', '_blank');
    if (pdfWindow) {
        pdfWindow.document.write('<html><head><title>Print Invoice</title>');
        pdfWindow.document.write('<script src="https://cdn.tailwindcss.com"></script>');
        pdfWindow.document.write('</head><body><div id="pdf-root"></div></body></html>');
        pdfWindow.document.close();

        const pdfRootEl = pdfWindow.document.getElementById('pdf-root');
        if (pdfRootEl) {
            const root = createRoot(pdfRootEl);
            root.render(<InvoicePDF order={order} vendorId={vendorId} statusData={statusData} />);
            setTimeout(() => {
                pdfWindow.print();
                pdfWindow.close();
            }, 500);
        }
    }
  };

  return (
    <div className="bg-gray-100 min-h-screen p-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Daily Report & Analysis</h1>
      </header>
      
      <section className="mb-8 bg-white p-6 rounded-lg shadow-md">
        <h2 className="text-2xl font-bold text-gray-700 mb-4 flex items-center"><BarChart className="mr-3" />Order Generation</h2>
        <div className="flex items-end space-x-4">
            <div className="flex-grow">
                <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Vendor (optional)</label>
                <Select
                    isMulti
                    options={vendorOptions}
                    onChange={(selected) => setVendorFilter(selected.map(s => s.value))}
                    placeholder="Default: All Vendors"
                />
            </div>
            <button
              onClick={() => onGenerate(vendorFilter)}
              disabled={isLoading}
              className="flex items-center justify-center px-6 py-3 bg-indigo-600 text-white font-bold rounded-lg shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-75 transition disabled:bg-indigo-300"
            >
              <RefreshCw size={20} className={`mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              {isLoading ? 'Optimizing...' : 'Generate / Regenerate Order'}
            </button>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-gray-700 mb-4 flex items-center"><FileText className="mr-3" />Generated Invoice Details</h2>
        <div className="bg-white p-6 rounded-lg shadow-md">
          {editableInvoice && Object.keys(editableInvoice.vendorOrders).length > 0 ? (
            <div>
              {Object.entries(editableInvoice.vendorOrders).map(([vendorId, order]) => (
                <div key={vendorId} className="mb-6 border-b pb-6 last:border-b-0">
                  <div className="md:flex justify-between items-center mb-4">
                    <h3 className="font-bold text-xl text-gray-800">{order.vendorName}</h3>
                    <div className="flex items-center space-x-2 mt-2 md:mt-0">
                        <select value={statusData[vendorId]?.status} onChange={e => handleStatusChange(vendorId, 'status', e.target.value)} className="p-1 border rounded-md text-sm">
                            <option>Pending</option>
                            <option>Reviewed</option>
                            <option>Approved</option>
                            <option>Modified</option>
                        </select>
                        <input type="text" placeholder="Your Name" value={statusData[vendorId]?.modifiedBy} onChange={e => handleStatusChange(vendorId, 'modifiedBy', e.target.value)} className="p-1 border rounded-md text-sm w-24"/>
                        <button onClick={() => handleSaveWrapper(vendorId, order)} className="p-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"><Save size={16}/></button>
                        
                        {statusData[vendorId]?.invoiceId && (
                            <button onClick={() => handleViewHistory(vendorId)} className="p-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"><History size={16}/></button>
                        )}
                        
                        <button 
                            onClick={() => handlePdfClick(order, vendorId)}
                            disabled={statusData[vendorId]?.status !== 'Approved'}
                            className="p-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
                        >
                            <FileDown size={16}/>
                        </button>
                    </div>
                  </div>
                  
                  {visibleLogVendorId === vendorId && invoiceLogs && invoiceLogs[statusData[vendorId].invoiceId] && (
                      <div className="my-4 p-4 bg-gray-50 rounded-lg border">
                          <h4 className="font-bold text-md mb-2">Status History</h4>
                          <ul className="space-y-1 text-sm text-gray-600 max-h-32 overflow-y-auto">
                              {invoiceLogs[statusData[vendorId].invoiceId].map((log, index) => (
                                  <li key={index} className="border-b last:border-b-0 py-1">
                                      <strong>{log.new_status}</strong> by {log.changed_by || 'N/A'} on {new Date(log.change_date).toLocaleString()}
                                  </li>
                              ))}
                          </ul>
                      </div>
                  )}

                  <ul className="mt-2 space-y-2 text-gray-600">
                    {order.items.map(item => (
                      <li key={item.id} className="flex justify-between items-center text-sm">
                        <span>{item.name} ({item.unit})</span>
                        <div className="flex items-center space-x-4">
                            <input type="number" value={item.quantity} onChange={(e) => handleQuantityChange(vendorId, item.id, parseInt(e.target.value, 10) || 0)} className="w-20 text-center p-1 border rounded-md"/>
                            <span className="font-medium w-20 text-right">${item.cost.toFixed(2)}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 text-sm space-y-2 text-right">
                      {order.bundleSavings > 0 && <div className="flex justify-end items-center text-green-600"><TrendingUp size={16} className="mr-2"/><span>Bundle Savings: <strong>${order.bundleSavings.toFixed(2)}</strong></span></div>}
                      <div className={`flex justify-end items-center ${order.shippingCost === 0 ? 'text-green-600' : 'text-red-600'}`}><Truck size={16} className="mr-2"/><span>Shipping Fee: <strong>${order.shippingCost.toFixed(2)}</strong></span></div>
                  </div>
                </div>
              ))}
              {calculatedTotals && <div className="mt-6 pt-4 border-t-2 border-dashed">
                <div className="flex justify-end items-center text-green-700 font-bold text-xl mb-2"><span>Total Savings: ${calculatedTotals.totalSavings.toFixed(2)}</span></div>
                <div className="text-right font-bold text-3xl text-gray-800">Final Total: ${calculatedTotals.totalCost.toFixed(2)}</div>
              </div>}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8"><p>{isLoading ? 'Generating...' : 'No order has been generated yet. Use the controls above to create an optimized order.'}</p></div>
          )}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-2xl font-bold text-gray-700 mb-4 flex items-center"><History className="mr-3" />Stock Movement Log</h2>
        <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-left text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                        <tr>
                            <th className="p-2">Date</th>
                            <th className="p-2">Item</th>
                            <th className="p-2">Type</th>
                            <th className="p-2 text-right">Quantity</th>
                            <th className="p-2">Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Array.isArray(movementLog) && movementLog.map((log, index) => (
                            <tr key={index} className="border-b">
                                <td className="p-2">{new Date(log.movement_date).toLocaleString()}</td>
                                <td className="p-2">{log.product_name}</td>
                                <td className="p-2">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                        log.movement_type === 'IN' ? 'bg-green-100 text-green-800' : 
                                        log.movement_type === 'OUT' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                                    }`}>
                                        {log.movement_type}
                                    </span>
                                </td>
                                <td className={`p-2 text-right font-bold ${log.quantity > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {log.quantity}
                                </td>
                                <td className="p-2">{log.description}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
      </section>
    </div>
  );
};

export default ReportPage;
