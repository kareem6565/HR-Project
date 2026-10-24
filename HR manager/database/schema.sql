-- ============================================================
--  Employee Attendance & Simple Payroll System — Schema
--  Compatible with MySQL 5.7+ / MariaDB 10.3+
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Database
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS `attendance_db`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `attendance_db`;

-- ------------------------------------------------------------
-- Table: categories (Employee Groups / Shifts)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `categories`;
CREATE TABLE `categories` (
  `id`                     INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  `name`                   VARCHAR(100)     NOT NULL,
  `shift_type`             ENUM('day','night') NOT NULL DEFAULT 'day',
  `work_start_time`        TIME             NOT NULL DEFAULT '09:00:00',
  `work_end_time`          TIME             NOT NULL DEFAULT '18:00:00',
  `break_start_time`       TIME             NOT NULL DEFAULT '13:00:00',
  `break_duration_minutes` INT UNSIGNED     NOT NULL DEFAULT 60,
  `cutoff_minutes`         INT UNSIGNED     NOT NULL DEFAULT 60,
  `center_latitude`        DECIMAL(10,7)    NOT NULL DEFAULT 24.7136000,
  `center_longitude`       DECIMAL(10,7)    NOT NULL DEFAULT 46.6753000,
  `allowed_radius_meters`  INT UNSIGNED     NOT NULL DEFAULT 300,
  `created_at`             TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Table: users
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id`                    INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  `emp_code`              VARCHAR(20)      NOT NULL UNIQUE,
  `name`                  VARCHAR(100)     NOT NULL,
  `password_hash`         VARCHAR(255)     NOT NULL,
  `role`                  ENUM('admin','hr','employee') NOT NULL DEFAULT 'employee',
  `category_id`           INT UNSIGNED     NULL DEFAULT NULL,
  `basic_salary`          DECIMAL(10,2)    NOT NULL DEFAULT 0.00,
  `yearly_vacation_days`  TINYINT UNSIGNED NOT NULL DEFAULT 21,
  `created_at`            TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_emp_code` (`emp_code`),
  CONSTRAINT `fk_users_category`
    FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Table: company_settings
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `company_settings`;
CREATE TABLE `company_settings` (
  `id`                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_name`           VARCHAR(150) NOT NULL DEFAULT 'My Company',
  `center_latitude`        DECIMAL(10,7) NOT NULL DEFAULT 24.7136000,
  `center_longitude`       DECIMAL(10,7) NOT NULL DEFAULT 46.6753000,
  `allowed_radius_meters`  INT UNSIGNED  NOT NULL DEFAULT 300,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Table: attendance
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `attendance`;
CREATE TABLE `attendance` (
  `id`                  INT UNSIGNED   NOT NULL AUTO_INCREMENT,
  `user_id`             INT UNSIGNED   NOT NULL,
  `date`                DATE           NOT NULL,
  `check_in_time`       TIME           NULL DEFAULT NULL,
  `check_out_time`      TIME           NULL DEFAULT NULL,
  `break_start_time`    TIME           NULL DEFAULT NULL,
  `break_end_time`      TIME           NULL DEFAULT NULL,
  `lat_in`              DECIMAL(10,7)  NULL DEFAULT NULL,
  `lng_in`              DECIMAL(10,7)  NULL DEFAULT NULL,
  `distance_in_meters`  INT            NULL DEFAULT NULL,
  `status`              ENUM('present','late','absent') NOT NULL DEFAULT 'present',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_date` (`user_id`, `date`),
  INDEX `idx_date` (`date`),
  CONSTRAINT `fk_attendance_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Table: work_submissions
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `work_submissions`;
CREATE TABLE `work_submissions` (
  `id`               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id`          INT UNSIGNED NOT NULL,
  `title`            VARCHAR(255) NOT NULL,
  `description`      TEXT NULL,
  `submission_type`  ENUM('pdf', 'image', 'text', 'link') NOT NULL DEFAULT 'text',
  `file_path`        VARCHAR(255) NULL,
  `external_link`    VARCHAR(255) NULL,
  `status`           ENUM('in_progress', 'completed', 'pending_review') NOT NULL DEFAULT 'completed',
  `admin_status`     ENUM('pending', 'approved', 'needs_revision') NOT NULL DEFAULT 'pending',
  `admin_feedback`   TEXT NULL,
  `submitted_at`     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_work_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
--  Seed Data
-- ============================================================

-- Company settings (Default HQ)
INSERT INTO `company_settings` (`company_name`, `center_latitude`, `center_longitude`, `allowed_radius_meters`)
VALUES ('شركة البيان للتقنية', 24.7136000, 46.6753000, 300);

-- Default Category
INSERT INTO `categories` (`name`, `work_start_time`, `work_end_time`, `break_start_time`, `break_duration_minutes`, `cutoff_minutes`, `center_latitude`, `center_longitude`, `allowed_radius_meters`)
VALUES ('الشفت الصباحي (الافتراضي)', '09:00:00', '18:00:00', '13:00:00', 60, 60, 24.7136000, 46.6753000, 300);

-- Default admin account (password: admin123)
INSERT INTO `users` (`emp_code`, `name`, `password_hash`, `role`, `category_id`, `basic_salary`, `yearly_vacation_days`)
VALUES (
  'ADM001',
  'System Administrator',
  '$2y$12$c6E.okZQSkylX0pqI7UROeJTm6kOYm72TWxpeJ8xG9FQSfeXNlBX6',
  'admin',
  NULL,
  15000.00,
  30
);

-- Sample employees (password: emp123)
INSERT INTO `users` (`emp_code`, `name`, `password_hash`, `role`, `category_id`, `basic_salary`, `yearly_vacation_days`) VALUES
('EMP001', 'Ahmed Al-Rashidi',    '$2y$12$g.Nshp5Zwoyy/wLLfgagIelvj9gHuAo8U8MYt3G0ey0ULa9t7TcXy', 'employee', 1, 8500.00, 21),
('EMP002', 'Fatima Al-Zahraa',   '$2y$12$g.Nshp5Zwoyy/wLLfgagIelvj9gHuAo8U8MYt3G0ey0ULa9t7TcXy', 'employee', 1, 7200.00, 21),
('EMP003', 'Omar Khalid',         '$2y$12$g.Nshp5Zwoyy/wLLfgagIelvj9gHuAo8U8MYt3G0ey0ULa9t7TcXy', 'employee', 1, 9000.00, 25),
('EMP004', 'Sara Al-Mutairi',    '$2y$12$g.Nshp5Zwoyy/wLLfgagIelvj9gHuAo8U8MYt3G0ey0ULa9t7TcXy', 'employee', 1, 6800.00, 21);
