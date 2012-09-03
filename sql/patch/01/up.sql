-- Modify user table to have graphtool user authentication

alter table `users` change `username` `username` varchar(128) not null;

alter table `users` add column `password` varchar(64) default null;
alter table `users` add column `salt` varchar(4) default null;

alter table `users` add column `first_name` varchar(128) default '';
alter table `users` add column `last_name` varchar(128) default '';
alter table `users` add column `force_pass_change` tinyint(1) default 0 after `last_name`;

alter table `users` add column `create_date` datetime default null;

alter table `users` add unique index `unique_username`(`username`);

-- opsview userid table

CREATE TABLE `opsview_users` (
  `id` int(11) unsigned NOT NULL auto_increment,
  `user_id` int(11) NOT NULL,
  `server_name` varchar(128) NOT NULL,
  `login_id` varchar(128) NOT NULL,
  `password` varchar(64) default NULL,
  `create_date`  datetime,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB;

alter table `opsview_users` add index `user_id_index` (user_id);
