import psycopg2
import time

class SQL:
    def __init__(self, **config):
        self.con = psycopg2.connect(**config)
        self.cur = self.con.cursor()
        self._reset()

    def _reset(self):
        self._cols, self._table, self._joins = '*', '', []
        self._where, self._params = '', ()
        self._order = ''

    def select(self, *cols):
        self._cols = ', '.join(cols) if cols else '*'
        return self

    def from_(self, table):
        self._table = table
        return self

    def where(self, cond, *params):
        self._where, self._params = f'WHERE {cond}', params
        return self

    def order_by(self, col, direction='ASC'):
        self._order = f'ORDER BY {col} {direction}'
        return self

    def join(self, table, on, type='INNER'):
        self._joins.append(f'{type} JOIN {table} ON {on}')
        return self

    def left_join(self, table, on):
        return self.join(table, on, 'LEFT')

    def build(self):
        sql = f'SELECT {self._cols} FROM {self._table}'
        if self._joins: sql += ' ' + ' '.join(self._joins)
        if self._where: sql += f' {self._where}'
        if self._order: sql += f' {self._order}'
        return sql, self._params

    def execute(self):
        sql, params = self.build()
        self.cur.execute(sql, params)
        self.con.commit()
        result = self.cur.fetchall()
        self._reset()
        return result

    def fetch(self):
        sql, params = self.build()
        self.cur.execute(sql, params)
        cols = [d[0] for d in self.cur.description]
        rows = self.cur.fetchall()
        self._reset()
        return [dict(zip(cols, r)) for r in rows]

    def insert(self, **values):
        cols = ', '.join(values.keys())
        placeholders = ', '.join(['%s'] * len(values))
        sql = f'INSERT INTO {self._table} ({cols}) VALUES ({placeholders}) RETURNING id'
        self.cur.execute(sql, tuple(values.values()))
        self.con.commit()
        return self.cur.fetchone()[0]

    def update(self, **values):
        set_clause = ', '.join([f'{k} = %s' for k in values.keys()])
        sql = f'UPDATE {self._table} SET {set_clause} {self._where}'
        self.cur.execute(sql, tuple(values.values()) + self._params)
        self.con.commit()
        rows = self.cur.rowcount
        self._reset()
        return rows

    def delete(self):
        sql = f'DELETE FROM {self._table} {self._where}'
        self.cur.execute(sql, self._params)
        self.con.commit()
        rows = self.cur.rowcount
        self._reset()
        return rows

    def raw(self, sql, params=()):
        self.cur.execute(sql, params)
        cols = [d[0] for d in self.cur.description]
        rows = self.cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

    def close(self):
        self.cur.close()
        self.con.close()


def timed(label, fn):
    start = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"\n{'='*60}")
    print(f"[{label}]  {elapsed:.2f} мс")
    if isinstance(result, list):
        for row in result[:3]:
            print(" ", row)
        print(f"Всего строк: {len(result)}")
    else:
        print(" ", result)
    return elapsed


db = SQL(host='localhost', port=5432, database='amazon_db', user='admin', password='12345')
db.cur.execute('SET search_path TO public')

TABLE = 'amazon_ecommerce'

times_no_index = {}

times_no_index[1] = timed(
    "Запрос 1 | Покупки из категории Electronics",
    lambda: db.from_(TABLE).select('*').where('category = %s', 'Electronics').fetch()
)

times_no_index[2] = timed(
    "Запрос 2 | Товары с рейтингом > 4.5",
    lambda: db.from_(TABLE).select('product_id', 'brand', 'rating').where('rating > %s', 4.5).fetch()
)

times_no_index[3] = timed(
    "Запрос 3 | Покупки из Bangalore по убыванию цены",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'final_price', 'location')
               .where('location = %s', 'Bangalore')
               .order_by('final_price', 'DESC')
               .fetch()
)

times_no_index[4] = timed(
    "Запрос 4 | Только возвращённые товары",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'is_returned', 'delivery_status')
               .where('is_returned = %s', True)
               .fetch()
)

times_no_index[5] = timed(
    "Запрос 5 | Среднее время доставки по городам",
    lambda: db.raw(
        f"SELECT location, ROUND(AVG(shipping_time_days)::numeric, 2) AS avg_days, COUNT(*) AS cnt "
        f"FROM {TABLE} GROUP BY location ORDER BY avg_days DESC"
    )
)

times_no_index[6] = timed(
    "Запрос 6 | Топ-10 брендов по кол-ву продаж",
    lambda: db.raw(
        f"SELECT brand, COUNT(*) AS sales FROM {TABLE} GROUP BY brand ORDER BY sales DESC LIMIT 10"
    )
)

times_no_index[7] = timed(
    "Запрос 7 | UPI-оплата и final_price > 20000",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'final_price', 'payment_method')
               .where('payment_method = %s AND final_price > %s', 'UPI', 20000)
               .fetch()
)

times_no_index[8] = timed(
    "Запрос 8 | Покупки за 2025-06-15",
    lambda: db.from_(TABLE).select('*').where('purchase_date = %s', '2025-06-15').fetch()
)

times_no_index[9] = timed(
    "Запрос 9 | Доставка > 7 дней и статус Delivered",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'shipping_time_days', 'delivery_status')
               .where('shipping_time_days > %s AND delivery_status = %s', 7, 'Delivered')
               .fetch()
)

times_no_index[10] = timed(
    "Запрос 10 | Subcategory=Mobile, discount > 15",
    lambda: db.from_(TABLE).select('product_id', 'brand', 'price', 'discount', 'final_price')
               .where('subcategory = %s AND discount > %s', 'Mobile', 15)
               .fetch()
)

indexes = [
    f"CREATE INDEX IF NOT EXISTS idx_category        ON {TABLE}(category)",
    f"CREATE INDEX IF NOT EXISTS idx_rating          ON {TABLE}(rating)",
    f"CREATE INDEX IF NOT EXISTS idx_location        ON {TABLE}(location)",
    f"CREATE INDEX IF NOT EXISTS idx_is_returned     ON {TABLE}(is_returned)",
    f"CREATE INDEX IF NOT EXISTS idx_payment_method  ON {TABLE}(payment_method)",
    f"CREATE INDEX IF NOT EXISTS idx_purchase_date   ON {TABLE}(purchase_date)",
    f"CREATE INDEX IF NOT EXISTS idx_shipping_status ON {TABLE}(shipping_time_days, delivery_status)",
    f"CREATE INDEX IF NOT EXISTS idx_subcategory     ON {TABLE}(subcategory)",
    f"CREATE INDEX IF NOT EXISTS idx_final_price     ON {TABLE}(final_price)",
    f"CREATE INDEX IF NOT EXISTS idx_brand           ON {TABLE}(brand)",
]

for sql in indexes:
    name = sql.split('idx_')[1].split(' ')[0]
    start = time.perf_counter()
    db.cur.execute(sql)
    db.con.commit()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"Индекс idx_{name:<20} создан за {elapsed:.1f} мс")

times_with_index = {}

times_with_index[1] = timed(
    "Запрос 1 | Покупки из категории Electronics",
    lambda: db.from_(TABLE).select('*').where('category = %s', 'Electronics').fetch()
)

times_with_index[2] = timed(
    "Запрос 2 | Товары с рейтингом > 4.5",
    lambda: db.from_(TABLE).select('product_id', 'brand', 'rating').where('rating > %s', 4.5).fetch()
)

times_with_index[3] = timed(
    "Запрос 3 | Покупки из Bangalore по убыванию цены",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'final_price', 'location')
               .where('location = %s', 'Bangalore')
               .order_by('final_price', 'DESC')
               .fetch()
)

times_with_index[4] = timed(
    "Запрос 4 | Только возвращённые товары",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'is_returned', 'delivery_status')
               .where('is_returned = %s', True)
               .fetch()
)

times_with_index[5] = timed(
    "Запрос 5 | Среднее время доставки по городам",
    lambda: db.raw(
        f"SELECT location, ROUND(AVG(shipping_time_days)::numeric, 2) AS avg_days, COUNT(*) AS cnt "
        f"FROM {TABLE} GROUP BY location ORDER BY avg_days DESC"
    )
)

times_with_index[6] = timed(
    "Запрос 6 | Топ-10 брендов по кол-ву продаж",
    lambda: db.raw(
        f"SELECT brand, COUNT(*) AS sales FROM {TABLE} GROUP BY brand ORDER BY sales DESC LIMIT 10"
    )
)

times_with_index[7] = timed(
    "Запрос 7 | UPI-оплата и final_price > 20000",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'final_price', 'payment_method')
               .where('payment_method = %s AND final_price > %s', 'UPI', 20000)
               .fetch()
)

times_with_index[8] = timed(
    "Запрос 8 | Покупки за 2025-06-15",
    lambda: db.from_(TABLE).select('*').where('purchase_date = %s', '2025-06-15').fetch()
)

times_with_index[9] = timed(
    "Запрос 9 | Доставка > 7 дней и статус Delivered",
    lambda: db.from_(TABLE).select('user_id', 'product_id', 'shipping_time_days', 'delivery_status')
               .where('shipping_time_days > %s AND delivery_status = %s', 7, 'Delivered')
               .fetch()
)

times_with_index[10] = timed(
    "Запрос 10 | Subcategory=Mobile, discount > 15",
    lambda: db.from_(TABLE).select('product_id', 'brand', 'price', 'discount', 'final_price')
               .where('subcategory = %s AND discount > %s', 'Mobile', 15)
               .fetch()
)

for i in range(1, 11):
    t1 = times_no_index[i]
    t2 = times_with_index[i]
    speedup = t1 / t2 if t2 > 0 else 0
    print(f"{i:<5} {t1:>12.2f}  {t2:>12.2f}  {speedup:>10.2f}x")

db.close()
