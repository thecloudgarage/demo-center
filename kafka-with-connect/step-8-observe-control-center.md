Observe via control center
```
Open http://<control-center-external-ip>:9021 in a browser.
Go to the ksqlDB section.
Select the cp-ksql-server cluster and use the SQL editor there to run ksqlDB queries.
```
register the orders stream (json example)
```
CREATE STREAM ORDERS_STREAM (
  order_id    STRING,
  customer_id INT,
  amount      DOUBLE,
  currency    STRING,
  status      STRING,
  event_ts    BIGINT
) WITH (
  KAFKA_TOPIC = 'orders',
  VALUE_FORMAT = 'JSON',
  TIMESTAMP = 'event_ts'
);
```
inspect live orders
```
SELECT * FROM ORDERS_STREAM EMIT CHANGES LIMIT 10;
```
filter only paid orders
```
CREATE STREAM ORDERS_PAID AS
  SELECT *
  FROM ORDERS_STREAM
  WHERE status = 'PAID'
  EMIT CHANGES;
```
This creates a new Kafka topic (by default ORDERS_PAID) that you can sink separately if desired.
Next we can create a hourly revenue per customer (table)
```
CREATE TABLE HOURLY_REVENUE_PER_CUSTOMER AS
  SELECT
    customer_id,
    WINDOWSTART AS window_start,
    WINDOWEND   AS window_end,
    SUM(amount) AS total_amount,
    COUNT(*)    AS order_count
  FROM ORDERS_STREAM
  WINDOW TUMBLING (SIZE 1 HOUR)
  GROUP BY customer_id
  EMIT CHANGES;
```
simple large order stream
```
CREATE STREAM LARGE_ORDERS AS
  SELECT *
  FROM ORDERS_STREAM
  WHERE amount > 250.0
  EMIT CHANGES;
```
