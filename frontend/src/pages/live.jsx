import React, { useState } from 'react';
import { ArrowDownRight, Calendar, ArrowUpRight, ArrowDownLeft } from 'lucide-react';

const getStockStatus = (item) => {
  if (item.remaining_stock < item.min_stock) return 'understock';
  if (item.remaining_stock > item.max_stock) return 'overstock';
  return 'optimal';
};

const statusStyles = {
  understock: { bgColor: 'bg-red-100', textColor: 'text-red-800', borderColor: 'border-red-500', barColor: 'bg-red-500' },
  overstock: { bgColor: 'bg-blue-100', textColor: 'text-blue-800', borderColor: 'border-blue-500', barColor: 'bg-blue-500' },
  optimal: { bgColor: 'bg-green-100', textColor: 'text-green-800', borderColor: 'border-green-500', barColor: 'bg-green-500' },
};

const StockItemCard = ({ item, onRecordMovement, isEditable }) => {
  const [amountOut, setAmountOut] = useState('');
  const status = getStockStatus(item);
  const styles = statusStyles[status];
  const percentage = Math.min((item.remaining_stock / item.max_stock) * 100, 100);

  const handleRecord = () => {
      const quantity = parseInt(amountOut, 10);
      if (!quantity || quantity <= 0) {
          alert('Please enter a valid positive number for stock out.');
          return;
      }
      onRecordMovement({
          productId: item.id,
          quantity: -quantity,
          movementType: 'OUT',
          description: 'Daily usage'
      });
      setAmountOut('');
  };

  return (
    <div className={`rounded-lg shadow-md p-4 flex flex-col ${styles.bgColor} border-l-4 ${styles.borderColor}`}>
      <img src={item.image_url} alt={item.name} className="w-full h-32 object-cover rounded-md mb-4" onError={(e) => { e.target.onerror = null; e.target.src='https://placehold.co/400x400/cccccc/000000?text=Image+Not+Found'; }}/>
      <div>
        <h3 className={`font-bold text-lg ${styles.textColor}`}>{item.name}</h3>
        <div className="text-2xl font-bold text-gray-700 my-2">
            {item.remaining_stock} <span className="text-lg font-medium text-gray-500">{item.unit}</span>
        </div>
        
        {/* Daily Stock In/Out Display */}
        <div className="flex justify-between text-sm mb-2">
            <span className="flex items-center text-green-600 font-medium">
                <ArrowUpRight size={16} className="mr-1"/> In: {item.daily_in}
            </span>
            <span className="flex items-center text-red-600 font-medium">
                <ArrowDownLeft size={16} className="mr-1"/> Out: {Math.abs(item.daily_out)}
            </span>
        </div>

        <p className={`text-sm font-medium ${styles.textColor}`}>{status.charAt(0).toUpperCase() + status.slice(1)}</p>
      </div>
      <div className="mt-4">
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div className={`${styles.barColor} h-2.5 rounded-full`} style={{ width: `${percentage}%` }}></div>
        </div>
        <p className="text-xs text-center mt-1 text-gray-500">Min: {item.min_stock} / Max: {item.max_stock}</p>
      </div>
      {isEditable && (
        <div className="mt-4 flex items-center space-x-2">
            <input
              type="number"
              placeholder="Amount Out"
              value={amountOut}
              onChange={(e) => setAmountOut(e.target.value)}
              className="w-full text-center p-2 border rounded-md focus:ring-2 focus:ring-indigo-500"
            />
            <button onClick={handleRecord} className="p-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
                <ArrowDownRight />
            </button>
        </div>
      )}
    </div>
  );
};

const LivePage = ({ stockItems, onRecordMovement, selectedDate, setSelectedDate, isToday }) => {
  return (
    <div className="relative min-h-screen bg-gray-100 p-6">
       <div className="mb-6 bg-white p-4 rounded-lg shadow-md flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-700">
            {isToday ? "Today's Stock Status" : `Viewing Stock for ${selectedDate}`}
          </h2>
          <div className="flex items-center space-x-2">
            <Calendar className="text-gray-500" />
            <input 
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="p-2 border rounded-md"
            />
          </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
        {stockItems.map(item => (
          <StockItemCard key={item.id} item={item} onRecordMovement={onRecordMovement} isEditable={isToday} />
        ))}
      </div>
    </div>
  );
};

export default LivePage;
