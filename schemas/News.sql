CREATE TABLE news (
    title character varying(255) NOT NULL,
    url character varying(255),
    description text,
    added integer,
    PRIMARY KEY (title)
);
