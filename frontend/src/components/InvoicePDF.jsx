import React from 'react';

// This is a presentational component for the printable invoice.
// It receives the invoice data as props and lays it out in a clean format.
const InvoicePDF = ({ order, vendorId, statusData }) => {
  if (!order) return null;

  const today = new Date().toLocaleDateString();

  return (
    <div className="p-8 bg-white text-gray-800 font-sans">
      <header className="flex justify-between items-center pb-4 border-b">
        <h1 className="text-4xl font-bold tracking-wider">INVOICE</h1>
        <div>
          <p><strong>Invoice No:</strong> #{statusData[vendorId]?.invoiceId || 'N/A'}</p>
          <p><strong>Date:</strong> {today}</p>
        </div>
      </header>

      <section className="my-8">
        <div className="grid grid-cols-2 gap-8">
          <div>
            <h2 className="font-bold mb-2">ISSUED TO:</h2>
            <p>Fried Chicken Restaurant</p>
            <p>123 Delicious St.</p>
            <p>Bangkok, Thailand</p>
          </div>
          <div>
            <h2 className="font-bold mb-2">PAY TO:</h2>
            <p>{order.vendorName}</p>
            <p>Account Name: {order.vendorName} Supplies</p>
            <p>Account No.: 123 4567 8901</p>
          </div>
        </div>
      </section>

      <section>
        <table className="w-full text-left">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-3 font-bold">DESCRIPTION</th>
              <th className="p-3 font-bold text-center">QTY</th>
              <th className="p-3 font-bold text-right">UNIT PRICE</th>
              <th className="p-3 font-bold text-right">TOTAL</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map(item => (
              <tr key={item.id} className="border-b">
                <td className="p-3">{item.name}</td>
                <td className="p-3 text-center">{item.quantity} {item.unit}</td>
                <td className="p-3 text-right">${item.price.toFixed(2)}</td>
                <td className="p-3 text-right">${item.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-8 text-right">
        <div className="w-1/3 ml-auto">
          <div className="flex justify-between">
            <p className="text-gray-600">Subtotal:</p>
            <p>${order.subtotal.toFixed(2)}</p>
          </div>
          <div className="flex justify-between">
            <p className="text-gray-600">Shipping:</p>
            <p>${order.shippingCost.toFixed(2)}</p>
          </div>
          <div className="flex justify-between mt-2 pt-2 border-t font-bold text-xl">
            <p>TOTAL:</p>
            <p>${(order.subtotal + order.shippingCost).toFixed(2)}</p>
          </div>
        </div>
      </section>

      <footer className="mt-24 text-center text-gray-500 text-sm">
        <p>Thank you for your business!</p>
      </footer>
    </div>
  );
};

export default InvoicePDF;
