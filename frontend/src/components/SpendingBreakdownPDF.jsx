import React from 'react';

const SpendingBreakdownPDF = ({ breakdownData, date }) => {
  if (!breakdownData || breakdownData.length === 0) {
    return <div className="p-8">No spending data available for this date.</div>;
  }

  const grandTotal = breakdownData.reduce((sum, vendorOrder) => sum + vendorOrder.totalCost, 0);

  return (
    <div className="p-8 bg-white text-gray-800 font-sans">
      <header className="pb-4 border-b mb-8">
        <h1 className="text-4xl font-bold tracking-wider">Daily Spending Report</h1>
        <p className="text-lg text-gray-600">Date: {new Date(date).toLocaleDateString()}</p>
      </header>

      {breakdownData.map((vendorOrder, index) => (
        <section key={index} className="mb-8">
          <h2 className="text-2xl font-bold text-gray-700 mb-3">{vendorOrder.vendorName}</h2>
          <table className="w-full text-left">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3 font-bold">ITEM</th>
                <th className="p-3 font-bold text-center">QTY</th>
                <th className="p-3 font-bold text-right">TOTAL COST</th>
              </tr>
            </thead>
            <tbody>
              {vendorOrder.items.map(item => (
                <tr key={item.id} className="border-b">
                  <td className="p-3">
                    {item.name}
                    {item.savings > 0 && (
                      <span className="text-xs text-green-600 ml-2">(Bundle Savings: ${item.savings.toFixed(2)})</span>
                    )}
                  </td>
                  <td className="p-3 text-center">{item.quantity} {item.unit}</td>
                  <td className="p-3 text-right">${item.cost.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-bold">
                <td colSpan="2" className="p-3 text-right">Subtotal:</td>
                <td className="p-3 text-right">${(vendorOrder.totalCost - vendorOrder.shippingCost).toFixed(2)}</td>
              </tr>
              <tr>
                <td colSpan="2" className="p-3 text-right">Shipping:</td>
                <td className="p-3 text-right">${vendorOrder.shippingCost.toFixed(2)}</td>
              </tr>
              <tr className="font-bold text-lg border-t-2">
                <td colSpan="2" className="p-3 text-right">Vendor Total:</td>
                <td className="p-3 text-right">${vendorOrder.totalCost.toFixed(2)}</td>
              </tr>
            </tfoot>
          </table>
        </section>
      ))}

      <section className="mt-12 text-right">
        <div className="w-1/2 ml-auto text-2xl font-bold">
          <div className="flex justify-between mt-2 pt-2 border-t-2 border-gray-800">
            <p>GRAND TOTAL:</p>
            <p>${grandTotal.toFixed(2)}</p>
          </div>
        </div>
      </section>

      <footer className="mt-24 text-center text-gray-500 text-sm">
        <p>This is an automatically generated report.</p>
      </footer>
    </div>
  );
};

export default SpendingBreakdownPDF;
