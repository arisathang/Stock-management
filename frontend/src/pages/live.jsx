import React, { useState, useEffect, useRef } from 'react';
import { Calendar } from 'lucide-react';

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

const StockItemCard = ({ item, onStockChange, isEditable }) => {
  const status = getStockStatus(item);
  const styles = statusStyles[status];
  const percentage = Math.min((item.remaining_stock / item.max_stock) * 100, 100);

  // --- Input Box Fix ---
  // 1. Use local state to manage the input value directly for a smooth typing experience.
  const [inputValue, setInputValue] = useState(item.remaining_stock);
  const debounceTimeout = useRef(null);

  // Update local state if the prop from parent changes (e.g., new date selected)
  useEffect(() => {
    setInputValue(item.remaining_stock);
  }, [item.remaining_stock]);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);

    // 2. "Debounce" the update to the parent component.
    // This clears the previous timer and sets a new one.
    // The onStockChange function is only called after the user stops typing for 500ms.
    clearTimeout(debounceTimeout.current);
    if (isEditable) {
        debounceTimeout.current = setTimeout(() => {
            onStockChange(item.id, parseInt(value, 10));
        }, 500); // 0.5 second delay
    }
  };

  return (
    <div className={`rounded-lg shadow-md p-4 flex flex-col justify-between ${styles.bgColor} border-l-4 ${styles.borderColor}`}>
      <img 
        src={item.image_url} 
        alt={item.name} 
        className="w-full h-32 object-cover rounded-md mb-4"
        onError={(e) => { e.target.onerror = null; e.target.src='https://placehold.co/400x400/cccccc/000000?text=Image+Not+Found'; }}
      />
      <div>
        <h3 className={`font-bold text-lg ${styles.textColor}`}>{item.name}</h3>
        <p className={`text-sm ${styles.textColor}`}>{status.charAt(0).toUpperCase() + status.slice(1)}</p>
      </div>
      <div className="mt-4">
        <div className="flex items-center justify-center">
          <input
            type="number"
            value={inputValue}
            onChange={handleInputChange}
            disabled={!isEditable} // Input is disabled for past dates
            className="w-24 text-center p-2 border rounded-md focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-200"
          />
          <span className={`ml-2 font-medium ${styles.textColor}`}>{item.unit}</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5 mt-3">
          <div className={`${styles.barColor} h-2.5 rounded-full`} style={{ width: `${percentage}%` }}></div>
        </div>
        <p className="text-xs text-center mt-1 text-gray-500">Min: {item.min_stock} / Max: {item.max_stock}</p>
      </div>
    </div>
  );
};

const LivePage = ({ stockItems, onStockChange, selectedDate, setSelectedDate, isToday }) => {
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
          <StockItemCard 
            key={item.id} 
            item={item} 
            onStockChange={onStockChange}
            isEditable={isToday} // Only allow editing for the current day
          />
        ))}
      </div>
    </div>
  );
};

export default LivePage;
