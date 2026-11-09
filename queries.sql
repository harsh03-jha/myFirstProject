-- ===== DML: UPDATE / DELETE =====
UPDATE product SET sell_price = sell_price * 1.05 WHERE category_id = 3;     -- 5% hike on jackets
UPDATE warehouse SET capacity = 7000 WHERE name = 'Pune Central';
DELETE FROM customer WHERE customer_id = 6;                                   -- customer with no dispatches

-- ===== SELECT / WHERE / ORDER BY =====
SELECT sku, name, size, color, sell_price FROM product WHERE color = 'Black' AND sell_price > 1500 ORDER BY sell_price DESC;

-- ===== GROUP BY + aggregates =====
SELECT c.name AS category, COUNT(DISTINCT p.product_id) AS items, SUM(i.quantity) AS units, SUM(i.quantity*p.cost_price) AS stock_value
FROM category c JOIN product p ON p.category_id=c.category_id JOIN inventory i ON i.product_id=p.product_id
GROUP BY c.category_id ORDER BY stock_value DESC;

-- ===== HAVING (low stock) =====
SELECT p.sku, p.name, SUM(i.quantity) AS total_qty, p.reorder_level
FROM product p JOIN inventory i ON i.product_id=p.product_id
GROUP BY p.product_id HAVING SUM(i.quantity) < p.reorder_level;

-- ===== JOIN (multi-table) =====
SELECT t.txn_id, t.txn_date, t.txn_type, p.sku, w.name AS warehouse, t.quantity, COALESCE(s.name, c.name) AS party
FROM stock_txn t JOIN product p ON p.product_id=t.product_id JOIN warehouse w ON w.warehouse_id=t.warehouse_id
LEFT JOIN supplier s ON s.supplier_id=t.supplier_id LEFT JOIN customer c ON c.customer_id=t.customer_id
ORDER BY t.txn_date;

-- ===== SUBQUERIES =====
SELECT name, sku FROM product WHERE product_id NOT IN (SELECT product_id FROM stock_txn WHERE txn_type='OUT');   -- never dispatched
SELECT sku, name, sell_price FROM product WHERE sell_price > (SELECT AVG(sell_price) FROM product);              -- above-average price
SELECT name FROM warehouse WHERE warehouse_id = (SELECT warehouse_id FROM inventory GROUP BY warehouse_id ORDER BY SUM(quantity) DESC LIMIT 1);

-- Supplier-wise purchase summary
SELECT s.name, COUNT(*) AS deliveries, SUM(t.quantity) AS units, SUM(t.quantity*p.cost_price) AS purchase_value
FROM stock_txn t JOIN supplier s ON s.supplier_id=t.supplier_id JOIN product p ON p.product_id=t.product_id
WHERE t.txn_type='IN' GROUP BY s.supplier_id ORDER BY purchase_value DESC;
