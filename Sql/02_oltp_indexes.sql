
CREATE INDEX idx_orders_customer_id
ON public.orders(customer_id);

CREATE INDEX idx_products_category_id
ON public.products(category_id);

CREATE INDEX idx_order_items_product_id
ON public.order_items(product_id);
