CREATE TABLE commandlog (
	ctime decimal(12, 2),
	irctype character varying(16) NOT NULL,
	network character varying(16) NOT NULL,
	channel character varying(32),
	user_nick character varying(64),
	user_host character varying(128),
	command character varying(128),
	PRIMARY KEY (ctime)
);
