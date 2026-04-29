
-- 1) 先看重複
SELECT trade_date, ticker, pattern, COUNT(*) AS cnt
FROM signals_history
GROUP BY trade_date, ticker, pattern
HAVING COUNT(*) > 1
ORDER BY cnt DESC, trade_date DESC;

-- 2) 刪除重複，只留一筆
DELETE FROM signals_history a
USING signals_history b
WHERE a.ctid < b.ctid
  AND a.trade_date = b.trade_date
  AND a.ticker = b.ticker
  AND a.pattern = b.pattern;

-- 3) 加唯一索引，封死未來重複
CREATE UNIQUE INDEX IF NOT EXISTS signals_history_uniq
ON signals_history (trade_date, ticker, pattern);

-- 4) 之後再考慮新增 framework 欄位（如果你要前端下拉選單更直觀）
-- ALTER TABLE signals_history ADD COLUMN IF NOT EXISTS framework text;
-- UPDATE signals_history SET framework = pattern WHERE framework IS NULL;
