CREATE TABLE torrents (
	added integer NOT NULL,
	url character varying(255) NOT NULL,
	description character varying(255) NOT NULL,
	PRIMARY KEY (url)
);
