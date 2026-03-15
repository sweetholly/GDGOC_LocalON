-- ============================================================
-- LOCAL ON — 최종 DDL v3 (확정)
-- MySQL 8.0 · 38 테이블
-- 기준: GPT v2 (S-DoT REGION 매핑) + area_hourly_timeseries 보강
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ============================================================
-- A. MASTER / INGESTION / MAPPING
-- ============================================================

CREATE TABLE IF NOT EXISTS `areas` (
    `area_id`       INT             NOT NULL AUTO_INCREMENT,
    `area_cd`       VARCHAR(10)     NOT NULL COMMENT 'POI001~POI120',
    `area_nm`       VARCHAR(100)    NOT NULL COMMENT 'citydata 호출 파라미터',
    `eng_nm`        VARCHAR(200)    NULL,
    `district`      VARCHAR(30)     NULL     COMMENT '자치구',
    `ui_category`   VARCHAR(30)     NULL     COMMENT '관광특구/고궁·문화유산/공원/발달상권/인구밀집지역',
    `lat`           DECIMAL(11,8)   NULL,
    `lng`           DECIMAL(11,8)   NULL,
    `radius_m`      INT             NOT NULL DEFAULT 500,
    `description`   TEXT            NULL,
    `is_active`     TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NULL     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`area_id`),
    UNIQUE KEY `uq_area_cd` (`area_cd`),
    UNIQUE KEY `uq_area_nm` (`area_nm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='서울시 주요 120장소 마스터';

CREATE TABLE IF NOT EXISTS `area_aliases` (
    `alias_id`      INT             NOT NULL AUTO_INCREMENT,
    `area_id`       INT             NOT NULL,
    `alias_type`    ENUM('display','search','legacy','map') NOT NULL DEFAULT 'search',
    `alias_value`   VARCHAR(200)    NOT NULL,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`alias_id`),
    KEY `idx_alias_area` (`area_id`),
    KEY `idx_alias_value` (`alias_value`),
    CONSTRAINT `fk_alias_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `collector_runs` (
    `run_id`        INT             NOT NULL AUTO_INCREMENT,
    `source_name`   VARCHAR(30)     NOT NULL COMMENT 'citydata / sdot',
    `started_at`    DATETIME        NOT NULL,
    `ended_at`      DATETIME        NULL,
    `status`        ENUM('running','success','partial','failed') NOT NULL DEFAULT 'running',
    `target_count`  INT             NULL,
    `success_count` INT             NULL DEFAULT 0,
    `fail_count`    INT             NULL DEFAULT 0,
    `error_message` TEXT            NULL,
    PRIMARY KEY (`run_id`),
    KEY `idx_collector_src_time` (`source_name`, `started_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `raw_citydata_responses` (
    `raw_id`            BIGINT      NOT NULL AUTO_INCREMENT,
    `area_id`           INT         NOT NULL,
    `request_area_nm`   VARCHAR(100) NOT NULL,
    `request_area_cd`   VARCHAR(10) NULL,
    `fetched_at`        DATETIME    NOT NULL,
    `result_code`       VARCHAR(20) NULL,
    `result_message`    VARCHAR(200) NULL,
    `payload_json`      JSON        NOT NULL,
    `payload_hash`      CHAR(64)    NULL,
    `created_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`raw_id`),
    KEY `idx_raw_city_area_time` (`area_id`, `fetched_at` DESC),
    CONSTRAINT `fk_raw_city_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_snapshots` (
    `snapshot_id`   BIGINT      NOT NULL AUTO_INCREMENT,
    `area_id`       INT         NOT NULL,
    `raw_id`        BIGINT      NULL,
    `area_cd`       VARCHAR(10) NOT NULL,
    `area_nm`       VARCHAR(100) NOT NULL,
    `replace_yn`    VARCHAR(1)  NULL,
    `fetched_at`    DATETIME    NOT NULL,
    `created_at`    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`snapshot_id`),
    UNIQUE KEY `uq_snap_area_fetched` (`area_id`, `fetched_at`),
    KEY `idx_snap_fetched` (`fetched_at` DESC),
    CONSTRAINT `fk_snap_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_snap_raw`  FOREIGN KEY (`raw_id`)  REFERENCES `raw_citydata_responses` (`raw_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `area_sdot_region_mappings` (
    `mapping_id`        INT         NOT NULL AUTO_INCREMENT,
    `area_id`           INT         NOT NULL,
    `sdot_region_key`   VARCHAR(50) NOT NULL COMMENT 'S-DoT REGION 값',
    `sdot_region_name`  VARCHAR(100) NULL,
    `is_primary`        TINYINT(1)  NOT NULL DEFAULT 0,
    `confidence`        DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    `note`              TEXT        NULL,
    `created_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME    NULL     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`mapping_id`),
    KEY `idx_sdot_map_region` (`sdot_region_key`),
    KEY `idx_sdot_map_area_pri` (`area_id`, `is_primary`),
    CONSTRAINT `fk_sdot_map_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S-DoT REGION ↔ area 매핑';

CREATE TABLE IF NOT EXISTS `raw_sdot_responses` (
    `raw_id`        BIGINT      NOT NULL AUTO_INCREMENT,
    `fetched_at`    DATETIME    NOT NULL,
    `payload_json`  JSON        NOT NULL,
    `payload_hash`  CHAR(64)    NULL,
    `created_at`    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`raw_id`),
    KEY `idx_raw_sdot_time` (`fetched_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S-DoT 원본 JSON 보관';

-- ============================================================
-- B. CITYDATA NORMALIZED — 1:1 Children
-- ============================================================

CREATE TABLE IF NOT EXISTS `citydata_live_population` (
    `snapshot_id`           BIGINT      NOT NULL,
    `source_updated_at`     DATETIME    NULL,
    `area_congest_lvl`      VARCHAR(10) NULL,
    `area_congest_msg`      TEXT        NULL,
    `area_ppltn_min`        INT         NULL,
    `area_ppltn_max`        INT         NULL,
    `male_ppltn_rate`       DECIMAL(5,2) NULL,
    `female_ppltn_rate`     DECIMAL(5,2) NULL,
    `ppltn_rate_0`          DECIMAL(5,2) NULL,
    `ppltn_rate_10`         DECIMAL(5,2) NULL,
    `ppltn_rate_20`         DECIMAL(5,2) NULL,
    `ppltn_rate_30`         DECIMAL(5,2) NULL,
    `ppltn_rate_40`         DECIMAL(5,2) NULL,
    `ppltn_rate_50`         DECIMAL(5,2) NULL,
    `ppltn_rate_60`         DECIMAL(5,2) NULL,
    `ppltn_rate_70`         DECIMAL(5,2) NULL,
    `resnt_ppltn_rate`      DECIMAL(5,2) NULL,
    `non_resnt_ppltn_rate`  DECIMAL(5,2) NULL,
    `fcst_yn`               VARCHAR(1)  NULL,
    `fcst_ppltn`            JSON        NULL,
    `fcst_time`             DATETIME    NULL,
    `fcst_congest_lvl`      VARCHAR(10) NULL,
    `fcst_ppltn_min`        INT         NULL,
    `fcst_ppltn_max`        INT         NULL,
    PRIMARY KEY (`snapshot_id`),
    CONSTRAINT `fk_pop_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_live_commercial_summary` (
    `snapshot_id`               BIGINT      NOT NULL,
    `source_updated_at`         DATETIME    NULL,
    `area_cmrcl_lvl`            VARCHAR(10) NULL,
    `area_sh_payment_cnt`       INT         NULL,
    `area_sh_payment_amt_min`   BIGINT      NULL,
    `area_sh_payment_amt_max`   BIGINT      NULL,
    `cmrcl_male_rate`           DECIMAL(5,2) NULL,
    `cmrcl_female_rate`         DECIMAL(5,2) NULL,
    `cmrcl_10_rate`             DECIMAL(5,2) NULL,
    `cmrcl_20_rate`             DECIMAL(5,2) NULL,
    `cmrcl_30_rate`             DECIMAL(5,2) NULL,
    `cmrcl_40_rate`             DECIMAL(5,2) NULL,
    `cmrcl_50_rate`             DECIMAL(5,2) NULL,
    `cmrcl_60_rate`             DECIMAL(5,2) NULL,
    `cmrcl_personal_rate`       DECIMAL(5,2) NULL,
    `cmrcl_corporation_rate`    DECIMAL(5,2) NULL,
    PRIMARY KEY (`snapshot_id`),
    CONSTRAINT `fk_cmrcl_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_road_summary` (
    `snapshot_id`           BIGINT      NOT NULL,
    `source_updated_at`     DATETIME    NULL,
    `road_traffic_spd`      DECIMAL(5,1) NULL,
    `road_traffic_idx`      VARCHAR(10) NULL,
    `road_msg`              TEXT        NULL,
    PRIMARY KEY (`snapshot_id`),
    CONSTRAINT `fk_road_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_weather_current` (
    `snapshot_id`       BIGINT      NOT NULL,
    `source_updated_at` DATETIME    NULL,
    `temp`              DECIMAL(4,1) NULL,
    `sensible_temp`     DECIMAL(4,1) NULL,
    `max_temp`          DECIMAL(4,1) NULL,
    `min_temp`          DECIMAL(4,1) NULL,
    `humidity`          INT         NULL,
    `wind_dirct`        VARCHAR(10) NULL,
    `wind_spd`          DECIMAL(4,1) NULL,
    `precipitation`     DECIMAL(5,1) NULL,
    `precpt_type`       VARCHAR(10) NULL,
    `pcp_msg`           TEXT        NULL,
    `sunrise`           VARCHAR(10) NULL,
    `sunset`            VARCHAR(10) NULL,
    `uv_index_lvl`      VARCHAR(10) NULL,
    `uv_index`          DECIMAL(4,1) NULL,
    `uv_msg`            TEXT        NULL,
    `pm25_index`        VARCHAR(10) NULL,
    `pm25`              DECIMAL(6,1) NULL,
    `pm10_index`        VARCHAR(10) NULL,
    `pm10`              DECIMAL(6,1) NULL,
    `air_idx`           VARCHAR(10) NULL,
    `air_idx_mvl`       DECIMAL(6,1) NULL,
    `air_idx_main`      VARCHAR(20) NULL,
    `air_msg`           TEXT        NULL,
    PRIMARY KEY (`snapshot_id`),
    CONSTRAINT `fk_weather_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- B-2. CITYDATA NORMALIZED — 1:N Children
-- ============================================================

CREATE TABLE IF NOT EXISTS `citydata_commercial_categories` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `rsb_lrg_ctgr` VARCHAR(50) NULL, `rsb_mid_ctgr` VARCHAR(50) NULL,
    `rsb_payment_lvl` VARCHAR(10) NULL, `rsb_sh_payment_cnt` INT NULL,
    `rsb_sh_payment_amt_min` BIGINT NULL, `rsb_sh_payment_amt_max` BIGINT NULL,
    `rsb_mct_cnt` INT NULL, `rsb_mct_time` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_cc_snap` (`snapshot_id`),
    CONSTRAINT `fk_cc_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_road_links` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `link_id` VARCHAR(20) NULL, `road_nm` VARCHAR(100) NULL,
    `start_nd_cd` VARCHAR(20) NULL, `start_nd_nm` VARCHAR(50) NULL, `start_nd_xy` VARCHAR(50) NULL,
    `end_nd_cd` VARCHAR(20) NULL, `end_nd_nm` VARCHAR(50) NULL, `end_nd_xy` VARCHAR(50) NULL,
    `dist` DECIMAL(10,2) NULL, `spd` DECIMAL(5,1) NULL, `idx` VARCHAR(10) NULL, `xylist` TEXT NULL,
    PRIMARY KEY (`id`), KEY `idx_rl_snap` (`snapshot_id`),
    CONSTRAINT `fk_rl_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_parking_lots` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `prk_cd` VARCHAR(20) NULL, `prk_nm` VARCHAR(100) NULL, `prk_type` VARCHAR(20) NULL,
    `cpcty` INT NULL, `cur_prk_cnt` INT NULL, `cur_prk_time` DATETIME NULL, `cur_prk_yn` VARCHAR(1) NULL,
    `pay_yn` VARCHAR(1) NULL, `rates` INT NULL, `time_rates` INT NULL, `add_rates` INT NULL, `add_time_rates` INT NULL,
    `road_addr` VARCHAR(200) NULL, `address` VARCHAR(200) NULL, `lat` DECIMAL(11,8) NULL, `lng` DECIMAL(11,8) NULL,
    PRIMARY KEY (`id`), KEY `idx_pk_snap` (`snapshot_id`),
    CONSTRAINT `fk_pk_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_subway_stations` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `sub_stn_nm` VARCHAR(50) NULL, `sub_stn_line` VARCHAR(10) NULL,
    `sub_stn_raddr` VARCHAR(200) NULL, `sub_stn_jibun` VARCHAR(200) NULL,
    `sub_stn_x` DECIMAL(11,8) NULL, `sub_stn_y` DECIMAL(11,8) NULL,
    `live_sub_ppltn` VARCHAR(50) NULL,
    `sub_acml_gton_ppltn_min` INT NULL, `sub_acml_gton_ppltn_max` INT NULL,
    `sub_acml_gtoff_ppltn_min` INT NULL, `sub_acml_gtoff_ppltn_max` INT NULL,
    `sub_30wthn_gton_ppltn_min` INT NULL, `sub_30wthn_gton_ppltn_max` INT NULL,
    `sub_30wthn_gtoff_ppltn_min` INT NULL, `sub_30wthn_gtoff_ppltn_max` INT NULL,
    `sub_10wthn_gton_ppltn_min` INT NULL, `sub_10wthn_gton_ppltn_max` INT NULL,
    `sub_10wthn_gtoff_ppltn_min` INT NULL, `sub_10wthn_gtoff_ppltn_max` INT NULL,
    `sub_5wthn_gton_ppltn_min` INT NULL, `sub_5wthn_gton_ppltn_max` INT NULL,
    `sub_5wthn_gtoff_ppltn_min` INT NULL, `sub_5wthn_gtoff_ppltn_max` INT NULL,
    `sub_stn_cnt` INT NULL, `sub_stn_time` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_ss_snap` (`snapshot_id`),
    CONSTRAINT `fk_ss_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_subway_arrivals` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `sub_stn_nm` VARCHAR(50) NULL, `sub_route_nm` VARCHAR(50) NULL, `sub_line` VARCHAR(10) NULL,
    `sub_ord` INT NULL, `sub_dir` VARCHAR(50) NULL, `sub_terminal` VARCHAR(50) NULL,
    `sub_arvtime` VARCHAR(20) NULL, `sub_armg1` VARCHAR(200) NULL, `sub_armg2` VARCHAR(200) NULL,
    `sub_arvinfo` VARCHAR(20) NULL, `sub_nt_stn` VARCHAR(20) NULL, `sub_bf_stn` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_sa_snap` (`snapshot_id`),
    CONSTRAINT `fk_sa_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_subway_facilities` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `sub_stn_nm` VARCHAR(50) NULL, `elvtr_nm` VARCHAR(100) NULL,
    `opr_sec` VARCHAR(100) NULL, `instl_pstn` VARCHAR(100) NULL,
    `use_yn` VARCHAR(10) NULL, `elvtr_se` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_sf_snap` (`snapshot_id`),
    CONSTRAINT `fk_sf_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_bus_stops` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `bus_stn_id` VARCHAR(20) NULL, `bus_ars_id` VARCHAR(20) NULL,
    `bus_stn_nm` VARCHAR(100) NULL, `bus_stn_x` DECIMAL(11,8) NULL, `bus_stn_y` DECIMAL(11,8) NULL,
    `live_bus_ppltn` VARCHAR(50) NULL,
    `bus_acml_gton_ppltn_min` INT NULL, `bus_acml_gton_ppltn_max` INT NULL,
    `bus_acml_gtoff_ppltn_min` INT NULL, `bus_acml_gtoff_ppltn_max` INT NULL,
    `bus_30wthn_gton_ppltn_min` INT NULL, `bus_30wthn_gton_ppltn_max` INT NULL,
    `bus_30wthn_gtoff_ppltn_min` INT NULL, `bus_30wthn_gtoff_ppltn_max` INT NULL,
    `bus_10wthn_gton_ppltn_min` INT NULL, `bus_10wthn_gton_ppltn_max` INT NULL,
    `bus_10wthn_gtoff_ppltn_min` INT NULL, `bus_10wthn_gtoff_ppltn_max` INT NULL,
    `bus_5wthn_gton_ppltn_min` INT NULL, `bus_5wthn_gton_ppltn_max` INT NULL,
    `bus_5wthn_gtoff_ppltn_min` INT NULL, `bus_5wthn_gtoff_ppltn_max` INT NULL,
    `bus_stn_cnt` INT NULL, `bus_stn_time` VARCHAR(20) NULL, `bus_result_msg` VARCHAR(200) NULL,
    PRIMARY KEY (`id`), KEY `idx_bs_snap` (`snapshot_id`),
    CONSTRAINT `fk_bs_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_accidents` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `acdnt_occr_dt` DATETIME NULL, `exp_clr_dt` DATETIME NULL,
    `acdnt_type` VARCHAR(30) NULL, `acdnt_dtype` VARCHAR(30) NULL, `acdnt_info` TEXT NULL,
    `acdnt_x` DECIMAL(11,8) NULL, `acdnt_y` DECIMAL(11,8) NULL, `acdnt_time` DATETIME NULL,
    PRIMARY KEY (`id`), KEY `idx_ac_snap` (`snapshot_id`),
    CONSTRAINT `fk_ac_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_ev_stations` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `stat_id` VARCHAR(20) NULL, `stat_nm` VARCHAR(100) NULL, `stat_addr` VARCHAR(200) NULL,
    `stat_x` DECIMAL(11,8) NULL, `stat_y` DECIMAL(11,8) NULL,
    `stat_usetime` VARCHAR(100) NULL, `stat_parkpay` VARCHAR(10) NULL,
    `stat_limityn` VARCHAR(10) NULL, `stat_limitdetail` VARCHAR(200) NULL, `stat_kinddetail` VARCHAR(50) NULL,
    PRIMARY KEY (`id`), KEY `idx_ev_stn_snap` (`snapshot_id`),
    CONSTRAINT `fk_ev_stn_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_ev_chargers` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `stat_id` VARCHAR(20) NULL, `charger_id` VARCHAR(20) NULL,
    `charger_type` VARCHAR(20) NULL, `charger_stat` VARCHAR(20) NULL,
    `statuppdt` DATETIME NULL, `lasttsdt` DATETIME NULL, `lasttedt` DATETIME NULL, `nowtsdt` DATETIME NULL,
    `output` VARCHAR(20) NULL, `method` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_ev_chg_snap` (`snapshot_id`),
    CONSTRAINT `fk_ev_chg_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_bike_stations` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `sbike_spot_id` VARCHAR(20) NULL, `sbike_spot_nm` VARCHAR(100) NULL,
    `sbike_shared` DECIMAL(5,2) NULL, `sbike_parking_cnt` INT NULL, `sbike_rack_cnt` INT NULL,
    `sbike_x` DECIMAL(11,8) NULL, `sbike_y` DECIMAL(11,8) NULL,
    PRIMARY KEY (`id`), KEY `idx_bk_snap` (`snapshot_id`),
    CONSTRAINT `fk_bk_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_weather_warnings` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `warn_val` VARCHAR(30) NULL, `warn_stress` VARCHAR(30) NULL,
    `announce_time` DATETIME NULL, `command` VARCHAR(20) NULL,
    `cancel_yn` VARCHAR(1) NULL, `warn_msg` TEXT NULL,
    PRIMARY KEY (`id`), KEY `idx_ww_snap` (`snapshot_id`),
    CONSTRAINT `fk_ww_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_weather_forecasts` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `fcst_dt` DATETIME NULL, `temp` DECIMAL(4,1) NULL, `precipitation` DECIMAL(5,1) NULL,
    `precpt_type` VARCHAR(10) NULL, `rain_chance` INT NULL, `sky_stts` VARCHAR(20) NULL,
    PRIMARY KEY (`id`), KEY `idx_wf_snap` (`snapshot_id`),
    CONSTRAINT `fk_wf_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_cultural_events` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `event_nm` VARCHAR(200) NULL, `event_period` VARCHAR(100) NULL,
    `event_place` VARCHAR(200) NULL, `event_x` DECIMAL(11,8) NULL, `event_y` DECIMAL(11,8) NULL,
    `pay_yn` VARCHAR(10) NULL, `thumbnail` TEXT NULL, `url` TEXT NULL, `event_etc_detail` TEXT NULL,
    PRIMARY KEY (`id`), KEY `idx_ce_snap` (`snapshot_id`),
    CONSTRAINT `fk_ce_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_disaster_messages` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `dst_se_nm` VARCHAR(30) NULL, `emrg_step_nm` VARCHAR(30) NULL, `msg_cn` TEXT NULL, `crt_dt` DATETIME NULL,
    PRIMARY KEY (`id`), KEY `idx_dm_snap` (`snapshot_id`),
    CONSTRAINT `fk_dm_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `citydata_yna_news` (
    `id` BIGINT NOT NULL AUTO_INCREMENT, `snapshot_id` BIGINT NOT NULL,
    `yna_step_nm` VARCHAR(30) NULL, `yna_ttl` VARCHAR(300) NULL, `yna_cn` TEXT NULL,
    `yna_ymd` VARCHAR(20) NULL, `yna_wrtr_nm` VARCHAR(50) NULL,
    PRIMARY KEY (`id`), KEY `idx_yn_snap` (`snapshot_id`),
    CONSTRAINT `fk_yn_snap` FOREIGN KEY (`snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- C. S-DoT NORMALIZED
-- ============================================================

CREATE TABLE IF NOT EXISTS `sdot_traffic_raw` (
    `id`                BIGINT      NOT NULL AUTO_INCREMENT,
    `sdot_region_key`   VARCHAR(50) NOT NULL COMMENT 'S-DoT REGION 값',
    `sdot_region_name`  VARCHAR(100) NULL,
    `area_id`           INT         NULL     COMMENT '매핑 성공 시',
    `visitor_count`     INT         NULL,
    `sensing_time`      DATETIME    NOT NULL,
    `fetched_at`        DATETIME    NULL,
    `source_serial`     VARCHAR(20) NULL     COMMENT '센서 시리얼 (보조)',
    `quality_flag`      VARCHAR(10) NULL,
    PRIMARY KEY (`id`),
    KEY `idx_sdot_region_time` (`sdot_region_key`, `sensing_time` DESC),
    KEY `idx_sdot_area_time` (`area_id`, `sensing_time` DESC),
    CONSTRAINT `fk_sdot_raw_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S-DoT 실시간 유동인구 raw';

CREATE TABLE IF NOT EXISTS `traffic_hourly_avg` (
    `id`                INT         NOT NULL AUTO_INCREMENT,
    `sdot_region_key`   VARCHAR(50) NOT NULL,
    `area_id`           INT         NULL,
    `day_of_week`       TINYINT     NOT NULL COMMENT '0=일~6=토',
    `hour`              TINYINT     NOT NULL COMMENT '0~23',
    `avg_count`         DECIMAL(10,2) NULL,
    `sample_weeks`      INT         NOT NULL DEFAULT 0,
    `updated_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_tha_region_dow_hr` (`sdot_region_key`, `day_of_week`, `hour`),
    KEY `idx_tha_area` (`area_id`),
    CONSTRAINT `fk_tha_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S-DoT hourly baseline (기존 명세 이름 유지)';

CREATE TABLE IF NOT EXISTS `sdot_sensor_meta` (
    `sensor_id`     INT         NOT NULL AUTO_INCREMENT,
    `serial`        VARCHAR(20) NOT NULL,
    `gu_name`       VARCHAR(30) NULL,
    `lat`           DECIMAL(11,8) NULL,
    `lng`           DECIMAL(11,8) NULL,
    `installed_at`  DATETIME    NULL,
    `is_active`     TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (`sensor_id`),
    UNIQUE KEY `uq_sensor_serial` (`serial`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S-DoT 센서 메타 (참조용)';

-- ============================================================
-- D. READ MODEL / SERVICE
-- ============================================================

CREATE TABLE IF NOT EXISTS `area_live_metrics` (
    `area_id`               INT         NOT NULL,
    `base_snapshot_id`      BIGINT      NULL,
    `base_time`             DATETIME    NULL,
    `congestion_level`      VARCHAR(10) NULL,
    `congestion_score`      DECIMAL(5,2) NULL,
    `citydata_score`        DECIMAL(5,2) NULL,
    `sdot_score`            DECIMAL(5,2) NULL,
    `congestion_msg`        TEXT        NULL,
    `sdot_current_count`    INT         NULL     COMMENT 'S-DoT 현재 유동인구',
    `sdot_baseline_count`   INT         NULL     COMMENT 'S-DoT 기준선 값',
    `sdot_region_key_used`  VARCHAR(50) NULL     COMMENT '사용된 REGION 키',
    `population_min`        INT         NULL,
    `population_max`        INT         NULL,
    `resident_rate`         DECIMAL(5,2) NULL,
    `non_resident_rate`     DECIMAL(5,2) NULL,
    `commercial_level`      VARCHAR(10) NULL,
    `payment_cnt`           INT         NULL,
    `payment_amt_min`       BIGINT      NULL,
    `payment_amt_max`       BIGINT      NULL,
    `weather_temp`          DECIMAL(4,1) NULL,
    `air_idx`               VARCHAR(10) NULL,
    `mapping_confidence`    DECIMAL(3,2) NULL,
    `is_estimated`          TINYINT(1)  NOT NULL DEFAULT 0,
    `updated_at`            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`area_id`),
    CONSTRAINT `fk_live_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_live_snap` FOREIGN KEY (`base_snapshot_id`) REFERENCES `citydata_snapshots` (`snapshot_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='현재 상태 통합 read model';

CREATE TABLE IF NOT EXISTS `area_population_baseline_5m` (
    `area_id`       INT             NOT NULL,
    `day_type`      ENUM('all','weekday','weekend','holiday') NOT NULL DEFAULT 'all',
    `slot_5m`       SMALLINT        NOT NULL COMMENT '0~287',
    `avg_ppltn_min` DECIMAL(10,2)   NULL,
    `avg_ppltn_max` DECIMAL(10,2)   NULL,
    `sample_days`   INT             NOT NULL DEFAULT 0,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`area_id`, `day_type`, `slot_5m`),
    CONSTRAINT `fk_bl_pop_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='citydata 인구 기준선 (5분, 28일)';

CREATE TABLE IF NOT EXISTS `area_commercial_baseline` (
    `area_id`               INT         NOT NULL,
    `day_of_week`           TINYINT     NOT NULL,
    `time_bucket`           VARCHAR(10) NOT NULL,
    `avg_payment_cnt`       DECIMAL(10,2) NULL,
    `avg_payment_amt_min`   DECIMAL(15,2) NULL,
    `avg_payment_amt_max`   DECIMAL(15,2) NULL,
    `sample_days`           INT         NOT NULL DEFAULT 0,
    `updated_at`            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`area_id`, `day_of_week`, `time_bucket`),
    CONSTRAINT `fk_bl_cmrcl_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='상권 기준선 (4주 동일 요일/시간대)';

CREATE TABLE IF NOT EXISTS `area_hourly_timeseries` (
    `id`                BIGINT      NOT NULL AUTO_INCREMENT,
    `area_id`           INT         NOT NULL,
    `stat_date`         DATE        NOT NULL,
    `hour`              TINYINT     NOT NULL COMMENT '0~23',
    `actual_count`      INT         NULL     COMMENT 'S-DoT 실측값',
    `baseline_count`    INT         NULL     COMMENT 'S-DoT 기준선',
    `citydata_ppltn_min` INT        NULL     COMMENT 'citydata 인구 최소',
    `citydata_ppltn_max` INT        NULL     COMMENT 'citydata 인구 최대',
    `congestion_level`  VARCHAR(10) NULL,
    `updated_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_ts_area_date_hr` (`area_id`, `stat_date`, `hour`),
    KEY `idx_ts_date` (`stat_date` DESC),
    CONSTRAINT `fk_ts_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='상세 시간대 그래프 (S-DoT + citydata 병기)';

CREATE TABLE IF NOT EXISTS `area_hourly_samples` (
    `sample_id`          BIGINT      NOT NULL AUTO_INCREMENT,
    `area_id`            INT         NOT NULL,
    `stat_date`          DATE        NOT NULL,
    `hour`               TINYINT     NOT NULL COMMENT '0~23',
    `sample_time`        DATETIME    NOT NULL,
    `actual_count`       INT         NULL,
    `baseline_count`     INT         NULL,
    `citydata_ppltn_min` INT         NULL,
    `citydata_ppltn_max` INT         NULL,
    `congestion_level`   VARCHAR(10) NULL,
    `is_estimated`       TINYINT(1)  NOT NULL DEFAULT 0,
    `created_at`         DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`sample_id`),
    KEY `idx_ahs_area_date_hour` (`area_id`, `stat_date`, `hour`),
    KEY `idx_ahs_area_sample_time` (`area_id`, `sample_time` DESC),
    CONSTRAINT `fk_ahs_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `trend_hot_places` (
    `snapshot_time`     DATETIME    NOT NULL,
    `area_id`           INT         NOT NULL,
    `rank`              TINYINT     NOT NULL,
    `rank_change`       TINYINT     NULL DEFAULT 0,
    `congestion_level`  VARCHAR(10) NULL,
    `congestion_score`  DECIMAL(5,2) NULL,
    `citydata_score`    DECIMAL(5,2) NULL,
    `sdot_score`        DECIMAL(5,2) NULL,
    `visitor_count`     INT         NULL,
    `updated_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`snapshot_time`, `rank`),
    KEY `idx_thp_area` (`area_id`),
    CONSTRAINT `fk_thp_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `trend_rising_regions` (
    `snapshot_time`     DATETIME    NOT NULL,
    `sdot_region_key`   VARCHAR(50) NOT NULL,
    `label`             VARCHAR(50) NULL,
    `visitor_avg`       INT         NULL,
    `change_pct`        DECIMAL(6,2) NULL,
    `change_label`      VARCHAR(20) NULL,
    `mapped_area_id`    INT         NULL,
    `updated_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`snapshot_time`, `sdot_region_key`),
    KEY `idx_trr_area` (`mapped_area_id`),
    CONSTRAINT `fk_trr_area` FOREIGN KEY (`mapped_area_id`) REFERENCES `areas` (`area_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='급상승 REGION 캐시 (S-DoT region 기준)';

CREATE TABLE IF NOT EXISTS `search_query_log` (
    `id`            BIGINT      NOT NULL AUTO_INCREMENT,
    `query`         VARCHAR(200) NOT NULL,
    `created_at`    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_sql_query` (`query`),
    KEY `idx_sql_created` (`created_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='사용자 검색어 로그';

-- ============================================================
-- E. OPTIONAL
-- ============================================================

CREATE TABLE IF NOT EXISTS `review_snapshots` (
    `id`            BIGINT      NOT NULL AUTO_INCREMENT,
    `area_id`       INT         NOT NULL,
    `review_count`  INT         NULL,
    `avg_rating`    DECIMAL(2,1) NULL,
    `source`        VARCHAR(30) NULL,
    `crawled_at`    DATETIME    NULL,
    PRIMARY KEY (`id`),
    KEY `idx_rv_area` (`area_id`, `crawled_at` DESC),
    CONSTRAINT `fk_rv_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`area_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `map_place_cache` (
    `id`                BIGINT      NOT NULL AUTO_INCREMENT,
    `query_key`         VARCHAR(200) NOT NULL,
    `map_place_id`      VARCHAR(30) NULL,
    `place_name`        VARCHAR(200) NULL,
    `lat`               DECIMAL(11,8) NULL,
    `lng`               DECIMAL(11,8) NULL,
    `payload_json`      JSON        NULL,
    `expires_at`        DATETIME    NULL,
    PRIMARY KEY (`id`),
    KEY `idx_mpc_query` (`query_key`),
    KEY `idx_mpc_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 완료: 38 테이블
-- Master/Mapping:  7  (areas, aliases, collector_runs, raw_citydata,
--                      snapshots, sdot_region_mappings, raw_sdot)
-- Citydata 1:1:    4  (population, commercial, road, weather)
-- Citydata 1:N:   16  (commercial_categories ~ yna_news)
-- S-DoT:           3  (sdot_traffic_raw, traffic_hourly_avg, sdot_sensor_meta)
-- Read Model:      6  (live_metrics, 2 baselines, hourly_timeseries, 2 trends)
-- Optional:        2  (review_snapshots, map_place_cache)
-- ============================================================
