-- MySQL dump 10.11
--
-- Host: localhost    Database: graphtool
-- ------------------------------------------------------
-- Server version	5.0.77

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `event_type`
--

DROP TABLE IF EXISTS `event_type`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `event_type` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `name` varchar(40) NOT NULL default '',
  `description` varchar(80) NOT NULL default '',
  `color` varchar(6) NOT NULL default 'FFA500',
  `alpha` int(11) unsigned NOT NULL default '10',
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM AUTO_INCREMENT=3 DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `events`
--

DROP TABLE IF EXISTS `events`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `events` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `node` varchar(80) NOT NULL default '',
  `event_type` int(11) unsigned NOT NULL default '1',
  `name` varchar(40) NOT NULL default '',
  `description` varchar(255) NOT NULL default '',
  `start_time` int(11) NOT NULL,
  `end_time` int(11) NOT NULL,
  `url` varchar(256) NOT NULL default '',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `graph`
--

DROP TABLE IF EXISTS `graph`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `graph` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `owner_id` int(11) unsigned NOT NULL,
  `graph_engine` varchar(40) NOT NULL default '',
  `graph_name` varchar(80) NOT NULL default '',
  `graph_title` varchar(80) NOT NULL default '',
  `graph_privacy` varchar(12) NOT NULL default 'Public',
  `graph_type` varchar(80) NOT NULL default '',
  `graph_dur_mod` varchar(1) NOT NULL default '-',
  `graph_dur_len` varchar(8) NOT NULL default '2',
  `graph_dur_unit` varchar(1) NOT NULL default 'd',
  `graph_start` int(11) unsigned NOT NULL default '0',
  `graph_create_date` int(11) unsigned NOT NULL,
  `events` varchar(12) NOT NULL default 'None',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `graph_parameters`
--

DROP TABLE IF EXISTS `graph_parameters`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `graph_parameters` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `graph_id` int(11) unsigned NOT NULL,
  `p_section` varchar(80) NOT NULL default '',
  `p_directive` varchar(80) NOT NULL default '',
  `p_value` varchar(80) NOT NULL default '',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `graph_series`
--

DROP TABLE IF EXISTS `graph_series`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `graph_series` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `graph_id` int(11) unsigned NOT NULL,
  `graph_seq_id` int(11) unsigned NOT NULL,
  `g_node` varchar(255) NOT NULL default '',
  `g_host` varchar(255) NOT NULL default '',
  `g_service` varchar(255) NOT NULL default '',
  `g_metric` varchar(255) NOT NULL default '',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `opsview_users`
--

DROP TABLE IF EXISTS `opsview_users`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `opsview_users` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `user_id` int(11) NOT NULL,
  `server_name` varchar(128) NOT NULL,
  `login_id` varchar(128) NOT NULL,
  `password` varchar(64) default NULL,
  `create_date` datetime default NULL,
  PRIMARY KEY  (`id`),
  KEY `user_id_index` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `suite`
--

DROP TABLE IF EXISTS `suite`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `suite` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `owner_id` int(11) NOT NULL,
  `name` varchar(40) NOT NULL,
  `title` varchar(80) NOT NULL,
  `dur_mod` varchar(1) NOT NULL,
  `dur_len` varchar(8) NOT NULL,
  `dur_unit` varchar(1) NOT NULL,
  `start` int(11) unsigned NOT NULL,
  `create_date` int(11) unsigned NOT NULL,
  `graphList` varchar(512) NOT NULL,
  `numCols` int(11) unsigned NOT NULL,
  `enableOverride` int(2) unsigned NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `id` (`id`),
  KEY `owner` (`owner_id`),
  KEY `start_date` (`start`),
  KEY `create_date` (`create_date`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `users` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `username` varchar(128) NOT NULL,
  `password` varchar(32) default NULL,
  `salt` varchar(4) default NULL,
  `first_name` varchar(128) default '',
  `last_name` varchar(128) default '',
  `force_pass_change` tinyint(1) default '0',
  `create_date` datetime default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `unique_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2012-08-28  1:08:45
