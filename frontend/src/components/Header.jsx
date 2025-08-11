import React from 'react';
import { ShoppingCart, Bell } from 'lucide-react';

const Header = ({ currentPage, onNavigate, alertCount, onToggleNotifications }) => {
  const NavLink = ({ pageName, children }) => {
    const isActive = currentPage === pageName.toLowerCase();
    return (
      <button
        onClick={() => onNavigate(pageName.toLowerCase())}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
          isActive
            ? 'bg-indigo-600 text-white'
            : 'text-gray-600 hover:bg-gray-200'
        }`}
      >
        {children}
      </button>
    );
  };

  return (
    <header className="bg-white shadow-sm p-4 flex justify-between items-center sticky top-0 z-20">
      <div className="flex items-center space-x-4">
        <div className="bg-indigo-600 p-2 rounded-lg">
          <ShoppingCart className="text-white" />
        </div>
        <h1 className="text-xl font-bold text-gray-800 hidden md:block">
          Stock Optimizer
        </h1>
      </div>

      <nav className="flex items-center space-x-2 bg-gray-100 p-1 rounded-lg">
        <NavLink pageName="Live">Live Status</NavLink>
        <NavLink pageName="Report">Daily Report</NavLink>
      </nav>

      <div className="relative">
        <button
          onClick={onToggleNotifications}
          className="relative p-2 rounded-full hover:bg-gray-200"
        >
          <Bell className="text-gray-600" />
          {alertCount > 0 && (
            <span className="absolute top-0 right-0 block h-3 w-3 rounded-full bg-red-500 border-2 border-white animate-pulse"></span>
          )}
        </button>
      </div>
    </header>
  );
};

export default Header;
