-- TUC MySQL setup. Run once:   mysql -u root < scripts/setup_mysql.sql
-- (If root has a password: mysql -u root -p < scripts/setup_mysql.sql)
-- Change the password here AND in .env (TUC_DATABASE_URL / TUC_TEST_DATABASE_URL).

CREATE DATABASE IF NOT EXISTS tuc
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS tuc_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Make sure existing databases also use utf8mb4 (safe to re-run).
ALTER DATABASE tuc      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER DATABASE tuc_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'tuc'@'localhost' IDENTIFIED BY 'change_me_tuc_password';
CREATE USER IF NOT EXISTS 'tuc'@'127.0.0.1' IDENTIFIED BY 'change_me_tuc_password';

GRANT ALL PRIVILEGES ON tuc.*      TO 'tuc'@'localhost';
GRANT ALL PRIVILEGES ON tuc.*      TO 'tuc'@'127.0.0.1';
GRANT ALL PRIVILEGES ON tuc_test.* TO 'tuc'@'localhost';
GRANT ALL PRIVILEGES ON tuc_test.* TO 'tuc'@'127.0.0.1';

FLUSH PRIVILEGES;
