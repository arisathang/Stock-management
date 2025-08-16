-- This script completely resets and initializes the database.

DROP TABLE IF EXISTS invoice_status_logs;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS stock_history;
DROP TABLE IF EXISTS vendor_products;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS products;

-- =================================================================
-- CREATE TABLES
-- =================================================================

CREATE TABLE products (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    image_url VARCHAR(1024),
    remaining_stock INT NOT NULL DEFAULT 0,
    min_stock INT NOT NULL,
    max_stock INT NOT NULL,
    last_year_prediction INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vendors (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    shipping_cost DECIMAL(10, 2) NOT NULL,
    free_shipping_threshold DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vendor_products (
    vendor_id VARCHAR(255) NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    bundles JSONB,
    PRIMARY KEY (vendor_id, product_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE stock_history (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(255) NOT NULL,
    record_date DATE NOT NULL,
    remaining_stock INT NOT NULL,
    UNIQUE(product_id, record_date),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    vendor_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending',
    modified_by VARCHAR(255),
    items JSONB,
    total_cost DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);

CREATE TABLE stock_movements (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    total_cost NUMERIC(10, 2) DEFAULT 0,
    movement_type VARCHAR(50) NOT NULL,
    description TEXT,
    movement_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE invoice_status_logs (
    id SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(255),
    change_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);


-- =================================================================
-- INSERT INITIAL DATA
-- =================================================================
INSERT INTO products (id, name, unit, image_url, remaining_stock, min_stock, max_stock, last_year_prediction) VALUES
('item1', 'Chicken', 'kg', '/item1.jpg', 100, 50, 200, 150),
('item2', 'Potatoes', 'kg', '/item2.jpg', 80, 40, 150, 120),
('item3', 'Flour', 'kg', '/item3.jpg', 50, 25, 100, 75),
('item4', 'Seasoning Powder', 'kg', '/item4.jpg', 20, 10, 40, 30),
('item5', 'Ketchup', 'liters', '/item5.jpg', 30, 15, 60, 40),
('item6', 'Chilli Sauce', 'liters', '/item6.jpg', 30, 15, 60, 40),
('item7', 'Cooking Oil', 'liters', '/item7.jpg', 60, 30, 120, 90),
('item8', 'Paper Bags', 'pcs', '/item8.jpg', 1000, 500, 3000, 2000),
('item9', 'Napkins', 'packs', '/item9.jpg', 50, 20, 100, 80),
('item10', 'Forks', 'pcs', '/item10.jpg', 800, 400, 2000, 1500);

INSERT INTO vendors (id, name, shipping_cost, free_shipping_threshold) VALUES
('vendor1', 'Poultry King', 30, 500),
('vendor2', 'Farm Fresh Produce', 20, 250),
('vendor3', 'Global Food Supplies', 40, 800),
('vendor4', 'Packaging & Co.', 25, 300);

-- More competitive pricing data
INSERT INTO vendor_products (vendor_id, product_id, price, bundles) VALUES
('vendor1', 'item1', 8.50, '[{"quantity": 50, "price": 400}]'),
('vendor1', 'item2', 1.30, NULL),
('vendor1', 'item3', 2.10, '[{"quantity": 25, "price": 50}]'),
('vendor1', 'item4', 15.50, NULL),
('vendor1', 'item5', 3.70, NULL),
('vendor1', 'item6', 3.90, NULL),
('vendor1', 'item7', 2.60, '[{"quantity": 60, "price": 150}]'),
('vendor1', 'item8', 0.12, NULL),
('vendor1', 'item9', 1.60, NULL),
('vendor1', 'item10', 0.06, NULL),
('vendor2', 'item1', 8.80, NULL),
('vendor2', 'item2', 1.20, '[{"quantity": 100, "price": 100}]'),
('vendor2', 'item3', 2.20, NULL),
('vendor2', 'item4', 16.00, '[{"quantity": 10, "price": 155}]'),
('vendor2', 'item5', 3.60, NULL),
('vendor2', 'item6', 3.85, '[{"quantity": 25, "price": 95}]'),
('vendor2', 'item7', 2.80, NULL),
('vendor2', 'item8', 0.14, NULL),
('vendor2', 'item9', 1.55, '[{"quantity": 50, "price": 75}]'),
('vendor2', 'item10', 0.07, NULL),
('vendor3', 'item1', 8.60, '[{"quantity": 60, "price": 480}]'),
('vendor3', 'item2', 1.25, NULL),
('vendor3', 'item3', 2.00, '[{"quantity": 50, "price": 90}]'),
('vendor3', 'item4', 15.00, NULL),
('vendor3', 'item5', 3.50, '[{"quantity": 20, "price": 65}]'),
('vendor3', 'item6', 3.80, '[{"quantity": 20, "price": 70}]'),
('vendor3', 'item7', 2.50, '[{"quantity": 50, "price": 120}]'),
('vendor3', 'item8', 0.11, '[{"quantity": 500, "price": 50}]'),
('vendor3', 'item9', 1.65, NULL),
('vendor3', 'item10', 0.06, '[{"quantity": 1000, "price": 55}]'),
('vendor4', 'item1', 9.20, NULL),
('vendor4', 'item2', 1.60, NULL),
('vendor4', 'item3', 2.40, NULL),
('vendor4', 'item4', 17.00, NULL),
('vendor4', 'item5', 3.55, '[{"quantity": 25, "price": 85}]'),
('vendor4', 'item6', 3.75, NULL),
('vendor4', 'item7', 2.90, NULL),
('vendor4', 'item8', 0.10, '[{"quantity": 1000, "price": 90}]'),
('vendor4', 'item9', 1.50, '[{"quantity": 100, "price": 140}]'),
('vendor4', 'item10', 0.05, '[{"quantity": 2000, "price": 95}]');

INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES
('item1', 50, 'IN', 'Received from Poultry King order #PK101', 425.00),
('item1', -15, 'OUT', 'Used for daily sales', 0),
('item2', -5, 'WASTE', 'Spoilage', 0);


-- =================================================================
-- POPULATE STOCK MOVEMENTS
-- =================================================================

-- Step 1: Set the initial stock on July 1st, 2025
INSERT INTO stock_movements (product_id, quantity, movement_type, description, movement_date) VALUES
('item1', 150, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item2', 120, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item3', 75, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item4', 30, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item5', 40, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item6', 40, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item7', 90, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item8', 2000, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item9', 80, 'IN', 'Initial Stock', '2025-07-01 08:00:00'),
('item10', 1500, 'IN', 'Initial Stock', '2025-07-01 08:00:00');

-- Step 2: Simulate daily usage (stock out) and deliveries (stock in)
INSERT INTO stock_movements (product_id, quantity, movement_type, description, movement_date, total_cost) VALUES
('item1', -20, 'OUT', 'Daily Sales', '2025-07-01 22:00:00', 0), ('item2', -15, 'OUT', 'Daily Sales', '2025-07-01 22:00:00', 0),
('item1', -22, 'OUT', 'Daily Sales', '2025-07-02 22:00:00', 0), ('item2', -18, 'OUT', 'Daily Sales', '2025-07-02 22:00:00', 0),
('item1', -18, 'OUT', 'Daily Sales', '2025-07-03 22:00:00', 0), ('item2', -12, 'OUT', 'Daily Sales', '2025-07-03 22:00:00', 0),
('item1', -25, 'OUT', 'Daily Sales', '2025-07-04 22:00:00', 0), ('item2', -20, 'OUT', 'Daily Sales', '2025-07-04 22:00:00', 0),
('item1', -30, 'OUT', 'Daily Sales', '2025-07-05 22:00:00', 0), ('item2', -25, 'OUT', 'Daily Sales', '2025-07-05 22:00:00', 0),
('item1', 150, 'IN', 'Delivery from Poultry King', '2025-07-07 09:00:00', 1275.00), ('item2', 120, 'IN', 'Delivery from Farm Fresh', '2025-07-07 09:00:00', 144.00),
('item1', -21, 'OUT', 'Daily Sales', '2025-07-08 22:00:00', 0), ('item2', -17, 'OUT', 'Daily Sales', '2025-07-08 22:00:00', 0),
('item1', -23, 'OUT', 'Daily Sales', '2025-07-09 22:00:00', 0), ('item2', -19, 'OUT', 'Daily Sales', '2025-07-09 22:00:00', 0),
('item1', -19, 'OUT', 'Daily Sales', '2025-07-10 22:00:00', 0), ('item2', -15, 'OUT', 'Daily Sales', '2025-07-10 22:00:00', 0),
('item1', -28, 'OUT', 'Daily Sales', '2025-07-11 22:00:00', 0), ('item2', -22, 'OUT', 'Daily Sales', '2025-07-11 22:00:00', 0),
('item1', -35, 'OUT', 'Daily Sales', '2025-07-12 22:00:00', 0), ('item2', -28, 'OUT', 'Daily Sales', '2025-07-12 22:00:00', 0),
('item1', 150, 'IN', 'Delivery from Poultry King', '2025-07-14 09:00:00', 1275.00), ('item2', 120, 'IN', 'Delivery from Farm Fresh', '2025-07-14 09:00:00', 144.00),
('item1', -20, 'OUT', 'Daily Sales', '2025-07-15 22:00:00', 0), ('item2', -16, 'OUT', 'Daily Sales', '2025-07-15 22:00:00', 0),
('item1', -18, 'OUT', 'Daily Sales', '2025-08-10 22:00:00', 0), ('item2', -14, 'OUT', 'Daily Sales', '2025-08-10 22:00:00', 0),
('item1', -19, 'OUT', 'Daily Sales', '2025-08-11 22:00:00', 0), ('item2', -16, 'OUT', 'Daily Sales', '2025-08-11 22:00:00', 0);

-- =================================================================
-- Step 3: Calculate and update the final remaining_stock in the products table
-- =================================================================
UPDATE products p
SET remaining_stock = COALESCE((
    SELECT SUM(m.quantity)
    FROM stock_movements m
    WHERE m.product_id = p.id
), 0);
