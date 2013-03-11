DROP TABLE IF EXISTS `torrent`;
CREATE TABLE `torrent` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `hash` varchar(40) NOT NULL,
  `name` varchar(300) DEFAULT NULL,
  `total_size_bytes` int(11) DEFAULT NULL,
  `retrieving_data` tinyint(1) NOT NULL DEFAULT '0',
  `base64_metadata` mediumtext,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `hash_UNIQUE` (`hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `file`;
CREATE TABLE `file` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `full_location` varchar(400) DEFAULT NULL,
  `length_bytes` int(11) NOT NULL DEFAULT '0',
  `torrent_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_file_1_idx` (`torrent_id`),
  CONSTRAINT `file_torrent_fk` FOREIGN KEY (`torrent_id`) REFERENCES `torrent` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `tracker`;
CREATE TABLE `tracker` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `torrent_id` int(11) NOT NULL,
  `tracker_url` varchar(200) NOT NULL,
  `seeds` int(11) NOT NULL DEFAULT '0',
  `leechers` int(11) NOT NULL DEFAULT '0',
  `completed` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `tracker_torrent_fk_idx` (`torrent_id`),
  CONSTRAINT `tracker_torrent_fk` FOREIGN KEY (`torrent_id`) REFERENCES `torrent` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

ALTER TABLE `tracker` ADD COLUMN `last_scrape` TIMESTAMP NULL  AFTER `completed` ;
ALTER TABLE `tracker` ADD COLUMN `scrape_error` VARCHAR(300) NULL  AFTER `last_scrape` ;

CREATE OR REPLACE VIEW `vw_scrape` AS
    select 
        `t`.`hash` AS `hash`,
        `t`.`id` AS `torrent_id`,
        `tr`.`id` AS `tracker_id`,
        `tr`.`tracker_url` AS `tracker_url`,
        `tr`.`last_scrape` AS `last_scrape`
    from
        (`torrent` `t`
        join `tracker` `tr`)
    where
        (isnull(`tr`.`last_scrape`)
            or (`tr`.`last_scrape` < (now() - interval 10 minute)))