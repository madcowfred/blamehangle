CREATE TABLE commandlog (
	ctime decimal(12, 2) NOT NULL,
	irctype character varying(16) NOT NULL,
	network character varying(16) NOT NULL,
	channel character varying(64),
	user_nick character varying(32),
	user_host character varying(128),
	command text,
	PRIMARY KEY (ctime)
);
