CREATE DATABASE db_bio;
CREATE DATABASE db_cms;

CREATE USER 'user'@'localhost' IDENTIFIED BY 'pass'

GRANT ALL PRIVILEGES ON db_bio.* TO 'user'@'localhost'
GRANT ALL PRIVILEGES ON db_cms.* TO 'user'@'localhost'
GRANT INSERT, DELETE, CREATE ROUTINE, ALTER ROUTINE, EXECUTE ON mysql.* TO 'user'@'localhost'
