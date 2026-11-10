
CHANGE TRACKING

-- Add updated_at to order_items
ALTER TABLE public.order_items
ADD COLUMN IF NOT EXISTS updated_at
TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;


-- Add updated_at to categories
ALTER TABLE public.categories
ADD COLUMN IF NOT EXISTS updated_at
TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;


TRIGGER FUNCTION

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


APPLY UPDATE TRIGGERS

-- 1. Customers
DROP TRIGGER IF EXISTS trg_customers_updated_at
ON public.customers;

CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON public.customers
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- 2. Products
DROP TRIGGER IF EXISTS trg_products_updated_at
ON public.products;

CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON public.products
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- 3. Orders
DROP TRIGGER IF EXISTS trg_orders_updated_at
ON public.orders;

CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- 4. Order Items
DROP TRIGGER IF EXISTS trg_order_items_updated_at
ON public.order_items;

CREATE TRIGGER trg_order_items_updated_at
BEFORE UPDATE ON public.order_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- 5. Categories
DROP TRIGGER IF EXISTS trg_categories_updated_at
ON public.categories;

CREATE TRIGGER trg_categories_updated_at
BEFORE UPDATE ON public.categories
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
