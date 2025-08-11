import React from 'react';
import { BarChart, FileText, RefreshCw, TrendingUp, Truck } from 'lucide-react';

const ReportPage = ({ invoice, onGenerate, isLoading }) => {
  return (
    <div className="bg-gray-100 min-h-screen p-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Daily Report & Analysis</h1>
      </header>
      
      <section className="mb-8">
        <h2 className="text-2xl font-bold text-gray-700 mb-4 flex items-center"><BarChart className="mr-3" />Order Options</h2>
        <div className="bg-white p-6 rounded-lg shadow-md">
          <p className="text-gray-600">Future development: This section can show alternative order options, such as prioritizing faster shipping over the absolute lowest cost.</p>
        </div>
      </section>

      <section>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-gray-700 flex items-center"><FileText className="mr-3" />Generated Invoice Details</h2>
          {!invoice && (
            <button
              onClick={onGenerate}
              disabled={isLoading}
              className="flex items-center justify-center px-6 py-3 bg-indigo-600 text-white font-bold rounded-lg shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-75 transition disabled:bg-indigo-300"
            >
              <RefreshCw size={20} className={`mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              {isLoading ? 'Optimizing...' : 'Generate Today\'s Order'}
            </button>
          )}
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          {invoice && Object.keys(invoice.vendorOrders).length > 0 ? (
            <div>
              {Object.entries(invoice.vendorOrders).map(([vendorId, order]) => (
                <div key={vendorId} className="mb-6 border-b pb-6 last:border-b-0">
                  <h3 className="font-bold text-xl text-gray-800 mb-3">{order.vendorName}</h3>
                  <ul className="mt-2 space-y-1 text-gray-600">
                    {order.items.map(item => (
                      <li key={item.id} className="flex justify-between text-sm">
                        <span>{item.name} ({item.quantity} {item.unit})</span>
                        <span className="font-medium">${item.cost.toFixed(2)}</span>
                      </li>
                    ))}
                  </ul>
                  {/* Savings Details per Vendor */}
                  <div className="mt-4 text-sm space-y-2 text-right">
                      {order.bundleSavings > 0 && (
                          <div className="flex justify-end items-center text-green-600">
                              <TrendingUp size={16} className="mr-2"/>
                              <span>Bundle Savings: <strong>${order.bundleSavings.toFixed(2)}</strong></span>
                          </div>
                      )}
                      {order.originalShippingCost > 0 && order.shippingCost === 0 && (
                           <div className="flex justify-end items-center text-green-600">
                              <Truck size={16} className="mr-2"/>
                              <span>Free Shipping Unlocked (Saved ${order.originalShippingCost.toFixed(2)})</span>
                          </div>
                      )}
                  </div>
                </div>
              ))}
              {/* Grand Total and Total Savings */}
              <div className="mt-6 pt-4 border-t-2 border-dashed">
                <div className="flex justify-end items-center text-green-700 font-bold text-xl mb-2">
                    <span>Total Savings: ${invoice.totalSavings.toFixed(2)}</span>
                </div>
                <div className="text-right font-bold text-3xl text-gray-800">
                    Final Total: ${invoice.totalCost.toFixed(2)}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              <p>{isLoading ? 'Generating...' : 'No order has been generated yet. Click the button above to create an optimized order.'}</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default ReportPage;
