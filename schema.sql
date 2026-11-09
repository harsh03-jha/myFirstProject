-- StyleStock WMS (SQLite). CREATE DATABASE equivalent: sqlite3 warehouse.db < schema.sql
-- On MySQL/PostgreSQL run first: CREATE DATABASE stylestock; USE stylestock;
PRAGMA foreign_keys = ON;

-- ===== DDL =====
CREATE TABLE category(
  category_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL CHECK(type IN ('Clothing','Footwear')));
CREATE TABLE supplier(
  supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, email TEXT UNIQUE, city TEXT NOT NULL);
CREATE TABLE warehouse(
  warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE, city TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity > 0));
CREATE TABLE customer(
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, city TEXT NOT NULL);
CREATE TABLE product(
  product_id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL, size TEXT NOT NULL, color TEXT NOT NULL,
  cost_price REAL NOT NULL CHECK(cost_price >= 0),
  sell_price REAL NOT NULL CHECK(sell_price >= cost_price),
  reorder_level INTEGER NOT NULL DEFAULT 10 CHECK(reorder_level >= 0),
  category_id INTEGER NOT NULL REFERENCES category(category_id) ON UPDATE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES supplier(supplier_id) ON UPDATE CASCADE);
CREATE TABLE inventory(
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  product_id INTEGER NOT NULL REFERENCES product(product_id),
  quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
  PRIMARY KEY(warehouse_id, product_id));
CREATE TABLE stock_txn(
  txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES product(product_id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
  txn_type TEXT NOT NULL CHECK(txn_type IN ('IN','OUT')),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  txn_date TEXT NOT NULL DEFAULT (date('now')),
  supplier_id INTEGER REFERENCES supplier(supplier_id),
  customer_id INTEGER REFERENCES customer(customer_id),
  CHECK((txn_type='IN' AND supplier_id IS NOT NULL AND customer_id IS NULL)
     OR (txn_type='OUT' AND customer_id IS NOT NULL AND supplier_id IS NULL)));

-- Trigger keeps inventory in sync; CHECK(quantity>=0) blocks overselling
CREATE TRIGGER trg_stock AFTER INSERT ON stock_txn
BEGIN
  INSERT OR IGNORE INTO inventory VALUES(NEW.warehouse_id, NEW.product_id, 0);
  UPDATE inventory SET quantity = quantity + CASE NEW.txn_type WHEN 'IN' THEN NEW.quantity ELSE -NEW.quantity END
  WHERE warehouse_id = NEW.warehouse_id AND product_id = NEW.product_id;
END;

ALTER TABLE customer ADD COLUMN email TEXT;   -- ALTER TABLE demo

-- ===== DML: INSERT (sample data) =====
INSERT INTO category(name,type) VALUES('T-Shirts','Clothing'),('Jeans','Clothing'),('Jackets','Clothing'),
 ('Sneakers','Footwear'),('Formal Shoes','Footwear'),('Sandals','Footwear');
INSERT INTO supplier(name,phone,email,city) VALUES
 ('Threadline Textiles','9800000001','sales@threadline.in','Pune'),
 ('DenimCo','9800000002','info@denimco.in','Ahmedabad'),
 ('Winterwear Mills','9800000003','orders@winterwear.in','Ludhiana'),
 ('StrideMakers','9800000004','hello@stridemakers.in','Agra'),
 ('Footprint Exports','9800000005','biz@footprint.in','Kanpur');
INSERT INTO warehouse(name,city,capacity) VALUES
 ('Pune Central','Pune',5000),('Mumbai Hub','Mumbai',8000),('Delhi North','Delhi',6000);
INSERT INTO customer(name,phone,city) VALUES
 ('Urban Threads Store','9700000001','Pune'),('Metro Fashion','9700000002','Mumbai'),
 ('Sole Mates','9700000003','Delhi'),('Trendy Hub','9700000004','Bengaluru'),
 ('Style Bazaar','9700000005','Jaipur'),('Fashion Point','9700000006','Nashik');
INSERT INTO product(sku,name,size,color,cost_price,sell_price,reorder_level,category_id,supplier_id) VALUES
 ('TS-BLK-M','Classic Crew T-Shirt','M','Black',250,499,20,1,1),
 ('TS-WHT-L','Classic Crew T-Shirt','L','White',250,499,15,1,1),
 ('JN-BLU-32','Slim Fit Jeans','32','Blue',700,1499,15,2,2),
 ('JK-GRY-L','Padded Jacket','L','Grey',1200,2599,10,3,3),
 ('JK-BLK-M','Bomber Jacket','M','Black',1100,2500,10,3,3),
 ('SN-WHT-9','Court Sneakers','9','White',900,1999,15,4,4),
 ('SN-BLK-8','Court Sneakers','8','Black',900,1999,15,4,4),
 ('JN-BLK-34','Slim Fit Jeans','34','Black',700,1499,15,2,2),
 ('FS-BRN-9','Derby Formal Shoes','9','Brown',1300,2799,8,5,5),
 ('SD-TAN-8','Leather Sandals','8','Tan',450,999,10,6,4);
-- Inward stock (inventory fills automatically via trigger)
INSERT INTO stock_txn(product_id,warehouse_id,txn_type,quantity,txn_date,supplier_id) VALUES
 (1,1,'IN',100,'2026-09-01',1),(2,1,'IN',60,'2026-09-01',1),(3,2,'IN',40,'2026-09-03',2),
 (4,2,'IN',35,'2026-09-05',3),(5,2,'IN',30,'2026-09-05',3),(6,3,'IN',70,'2026-09-08',4),
 (7,3,'IN',45,'2026-09-08',4),(8,1,'IN',40,'2026-09-10',2),(9,3,'IN',30,'2026-09-12',5),
 (10,2,'IN',25,'2026-09-12',4);
-- Outward stock (dispatch to customers)
INSERT INTO stock_txn(product_id,warehouse_id,txn_type,quantity,txn_date,customer_id) VALUES
 (1,1,'OUT',30,'2026-09-15',1),(4,2,'OUT',20,'2026-09-16',2),(2,1,'OUT',50,'2026-09-18',3),
 (7,3,'OUT',40,'2026-09-20',4),(6,3,'OUT',15,'2026-09-21',5);
