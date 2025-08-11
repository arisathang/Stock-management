import React from 'react';
import {
  ShoppingCart,
  BarChart,
  FileText,
  Package,
  AlertCircle,
  ArrowLeft,
  Bell,
  RefreshCw,
  Truck,
  DollarSign,
} from 'lucide-react';

// A mapping of icon names to their respective components
const iconMap = {
  shoppingCart: ShoppingCart,
  barChart: BarChart,
  fileText: FileText,
  package: Package,
  alertCircle: AlertCircle,
  arrowLeft: ArrowLeft,
  bell: Bell,
  refresh: RefreshCw,
  truck: Truck,
  dollarSign: DollarSign,
};

/**
 * A dynamic icon component that renders an icon based on its name.
 * @param {string} name - The name of the icon to render (e.g., 'shoppingCart').
 * @param {string} [className] - Optional additional CSS classes.
 * @param {number} [size=24] - The size of the icon.
 */
const Icon = ({ name, className, size = 24, ...props }) => {
  const LucideIcon = iconMap[name];

  if (!LucideIcon) {
    // Return a default icon or null if the name is not found
    console.warn(`Icon with name "${name}" not found.`);
    return <Package size={size} className={className} {...props} />;
  }

  return <LucideIcon size={size} className={className} {...props} />;
};

export default Icon;
