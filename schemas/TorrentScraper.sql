CREATE TABLE torrents (
	scrape_time integer NOT NULL,
	url character varying(255) NOT NULL PRIMARY KEY,
	filename character varying(255),
	filesize bigint
);
